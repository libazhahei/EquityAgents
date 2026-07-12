"""Main orchestrator for Deep Equity Research workflow."""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.prebuilt import ToolNode

from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.graph.checkpointer import (
    get_equity_checkpointer,
    make_thread_id,
    register_run,
    upsert_run_edge,
)
from tradingagents.equity_research.graph.human_review import (
    default_hr2_patch,
    load_human_review_json,
    patches_for_interrupt,
)
from tradingagents.equity_research.graph.propagation import EquityPropagator
from tradingagents.equity_research.graph.setup import EquityGraphSetup
from tradingagents.equity_research.runtime.progress import ProgressBus
from tradingagents.equity_research.storage.db import init_db
from tradingagents.llm_clients import create_llm_client

logger = logging.getLogger(__name__)


def _cache_root_for_checkpointer(config: dict[str, Any]) -> Path:
    """Root passed to get_equity_checkpointer (appends checkpoints/equity_research)."""
    er = config.get("equity_research", {}) or {}
    explicit = er.get("checkpoint_dir")
    if explicit:
        p = Path(explicit)
        # Allow either cache root or the equity_research checkpoints folder itself.
        if p.name == "equity_research" and p.parent.name == "checkpoints":
            return p.parent.parent
        return p
    return Path(
        config.get("data_cache_dir")
        or os.path.join(os.path.expanduser("~"), ".tradingagents", "cache")
    )


class EquityResearchGraph:
    """Hypothesis-driven equity research workflow (MVP1 research spine)."""

    def __init__(
        self,
        debug: bool = False,
        config: dict[str, Any] | None = None,
        callbacks: list | None = None,
        init_database: bool = True,
        progress_bus: ProgressBus | None = None,
    ):
        self.debug = debug
        self.config = config or DEFAULT_CONFIG.copy()
        self.callbacks = callbacks or []
        self.progress_bus = progress_bus or ProgressBus()
        set_config(self.config)

        os.makedirs(self.config.get("results_dir", "."), exist_ok=True)
        er_results = self.config.get(
            "equity_research_results_dir",
            os.path.join(os.path.expanduser("~"), ".tradingagents", "equity_research"),
        )
        os.makedirs(er_results, exist_ok=True)

        if init_database:
            try:
                init_db(self.config)
            except Exception as exc:
                logger.warning("Database init failed (continuing): %s", exc)

        llm_kwargs = self._get_provider_kwargs()
        if self.callbacks:
            llm_kwargs["callbacks"] = self.callbacks

        deep_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["deep_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        quick_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config["quick_think_llm"],
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )
        nano_client = create_llm_client(
            provider=self.config["llm_provider"],
            model=self.config.get("nano_think_llm", "gpt-5.4-nano"),
            base_url=self.config.get("backend_url"),
            **llm_kwargs,
        )

        self.deps = EquityResearchDeps(
            config=self.config,
            deep_llm=deep_client.get_llm(),
            quick_llm=quick_client.get_llm(),
            nano_llm=nano_client.get_llm(),
            progress_bus=self.progress_bus,
        )
        self.propagator = EquityPropagator(
            max_recur_limit=self.config.get("equity_research", {}).get("max_recur_limit", 100),
        )
        # Compiled lazily in propagate when checkpointer is bound to ticker.
        self.graph = None
        self._workflow = EquityGraphSetup(self.deps)
        self.curr_state = None
        self.ticker = None
        self._checkpointer_ctx = None

    def _get_provider_kwargs(self) -> dict[str, Any]:
        """Get provider-specific kwargs for LLM client creation."""
        kwargs = {}
        provider = self.config.get("llm_provider", "").lower()

        if provider == "google":
            thinking_level = self.config.get("google_thinking_level")
            if thinking_level:
                kwargs["thinking_level"] = thinking_level

        elif provider == "openai":
            reasoning_effort = self.config.get("openai_reasoning_effort")
            if reasoning_effort:
                kwargs["reasoning_effort"] = reasoning_effort

        elif provider == "anthropic":
            effort = self.config.get("anthropic_effort")
            if effort:
                kwargs["effort"] = effort

        temperature = self.config.get("temperature")
        if temperature is not None and temperature != "":
            kwargs["temperature"] = float(temperature)

        return kwargs

    def _er_cfg(self) -> dict[str, Any]:
        return self.config.get("equity_research", {}) or {}

    def _compile_graph(self, checkpointer=None):
        workflow = EquityGraphSetup(self.deps, checkpointer=checkpointer).setup_graph()
        interrupt = bool(self._er_cfg().get("human_review_interrupt", True))
        if checkpointer is not None and interrupt:
            return workflow.compile(
                checkpointer=checkpointer,
                interrupt_before=["human_review_1", "human_review_2"],
            )
        if checkpointer is not None:
            return workflow.compile(checkpointer=checkpointer)
        return workflow.compile()

    def subscribe_progress(self, sink) -> Any:
        return self.progress_bus.subscribe(sink)

    def iter_progress(self):
        return self.progress_bus.iter_events()

    def _next_gate(self, snap) -> str | None:
        nxt = getattr(snap, "next", None) or ()
        if not nxt:
            return None
        names = list(nxt) if isinstance(nxt, (tuple, list)) else [nxt]
        for name in names:
            if name in ("human_review_1", "human_review_2"):
                return str(name)
        return str(names[0]) if names else None

    def _drive_with_human_resume(
        self,
        *,
        init_state: dict[str, Any],
        invoke_config: dict[str, Any],
        human_review: dict[str, Any] | None,
        auto_resume_human: bool,
        checkpointer=None,
    ) -> dict[str, Any]:
        graph = self.graph
        assert graph is not None
        bus = self.progress_bus
        thread_id = invoke_config.get("configurable", {}).get("thread_id", "")

        final_state = graph.invoke(init_state, invoke_config)

        while True:
            snap = graph.get_state(invoke_config)
            gate = self._next_gate(snap)
            if not gate:
                break
            if gate not in ("human_review_1", "human_review_2"):
                break
            if not auto_resume_human:
                bus.emit(
                    stage=gate,
                    node=gate,
                    status="interrupted",
                    run_id=str(init_state.get("run_id", "")),
                    thread_id=thread_id,
                    ticker=str(init_state.get("ticker", "")),
                )
                values = snap.values if hasattr(snap, "values") else final_state
                return values if isinstance(values, dict) else (final_state or {})

            bus.emit(
                stage=gate,
                node=gate,
                status="waiting_human",
                run_id=str(init_state.get("run_id", "")),
                thread_id=thread_id,
                ticker=str(init_state.get("ticker", "")),
            )
            patch_update = patches_for_interrupt(
                human_review,
                gate,  # type: ignore[arg-type]
                config=self.config,
            )
            if gate == "human_review_2" and "selected_section_ids" not in (
                patch_update.get("human_review_2_patch") or {}
            ):
                patch_update.setdefault("human_review_2_patch", {}).update(
                    default_hr2_patch(self.config)
                )
            graph.update_state(invoke_config, patch_update)
            bus.emit(
                stage=gate,
                node=gate,
                status="resumed",
                run_id=str(init_state.get("run_id", "")),
                thread_id=thread_id,
                ticker=str(init_state.get("ticker", "")),
            )
            if checkpointer is not None:
                try:
                    upsert_run_edge(
                        checkpointer,
                        run_id=str(init_state.get("run_id", "")),
                        ticker=str(init_state.get("ticker", "")),
                        as_of_date=str(init_state.get("trade_date", "")),
                        node_path=gate,
                        status="resumed",
                    )
                except Exception:
                    pass
            final_state = graph.invoke(None, invoke_config)

        snap = graph.get_state(invoke_config)
        if snap and getattr(snap, "values", None):
            return snap.values
        return final_state or {}

    def propagate(
        self,
        ticker: str,
        trade_date: str,
        *,
        run_id: str | None = None,
        human_review: dict[str, Any] | str | Path | None = None,
        auto_resume_human: bool = True,
        **kwargs: Any,
    ) -> tuple[dict[str, Any], str]:
        """Run equity research spine for a ticker.

        ``human_review`` may be a path to JSON or an already-loaded dict.
        When ``auto_resume_human`` is True (CLI default), HR interrupts are
        resumed with JSON patches or passthrough defaults.
        """
        self.ticker = ticker.upper()
        run_id = run_id or str(uuid.uuid4())
        if isinstance(human_review, (str, Path)):
            human_review = load_human_review_json(human_review)

        init_state = self.propagator.create_initial_state(
            self.ticker,
            trade_date=trade_date,
            run_id=run_id,
            _thread_id="",  # filled below
            **kwargs,
        )

        er = self._er_cfg()
        checkpoint_enabled = bool(er.get("checkpoint_enabled", True))
        cache_root = _cache_root_for_checkpointer(self.config)

        thread_id = make_thread_id(self.ticker, trade_date, run_id)
        init_state["_thread_id"] = thread_id

        final_state: dict[str, Any] | None = None
        saver = None
        try:
            if checkpoint_enabled:
                self._checkpointer_ctx = get_equity_checkpointer(cache_root, self.ticker)
                saver = self._checkpointer_ctx.__enter__()
                register_run(
                    saver,
                    run_id=run_id,
                    ticker=self.ticker,
                    as_of_date=trade_date,
                    status="running",
                )
                self.graph = self._compile_graph(checkpointer=saver)
                invoke_args = self.propagator.get_graph_args(
                    self.callbacks, thread_id=thread_id
                )
                invoke_config = invoke_args["config"]
                final_state = self._drive_with_human_resume(
                    init_state=init_state,
                    invoke_config=invoke_config,
                    human_review=human_review if isinstance(human_review, dict) else None,
                    auto_resume_human=auto_resume_human,
                    checkpointer=saver,
                )
                try:
                    upsert_run_edge(
                        saver,
                        run_id=run_id,
                        ticker=self.ticker,
                        as_of_date=trade_date,
                        node_path="root",
                        status="succeeded",
                    )
                except Exception:
                    pass
            else:
                self.graph = self._compile_graph(checkpointer=None)
                # Without checkpointer, interrupts cannot pause — apply defaults upfront.
                if human_review and isinstance(human_review, dict):
                    init_state.update(
                        patches_for_interrupt(human_review, "human_review_1", config=self.config)
                    )
                    init_state.update(
                        patches_for_interrupt(human_review, "human_review_2", config=self.config)
                    )
                else:
                    init_state["human_review_2_patch"] = default_hr2_patch(self.config)
                args = self.propagator.get_graph_args(self.callbacks)
                if self.debug:
                    for state in self.graph.stream(init_state, **args):
                        final_state = state
                else:
                    final_state = self.graph.invoke(init_state, **args)
        except Exception:
            if saver is not None:
                try:
                    upsert_run_edge(
                        saver,
                        run_id=run_id,
                        ticker=self.ticker,
                        as_of_date=trade_date,
                        node_path="root",
                        status="failed",
                    )
                except Exception:
                    pass
            raise
        finally:
            if self._checkpointer_ctx is not None:
                self._checkpointer_ctx.__exit__(None, None, None)
                self._checkpointer_ctx = None

        self.curr_state = final_state
        self._save_state_log(final_state)
        if not final_state:
            return {}, ""
        outputs = final_state.get("section_research_outputs") or {}
        summary = ""
        if outputs:
            first = next(iter(outputs.values()), {})
            summary = str(first.get("final_section_text") or first.get("executive_summary") or "")[:500]
        elif final_state.get("consensus_report"):
            summary = str(final_state["consensus_report"])[:500]
        return final_state, summary

    def _save_state_log(self, state: dict[str, Any] | None) -> None:
        if not state:
            return
        ticker = state.get("ticker", "UNKNOWN")
        report_id = state.get("report_id", datetime.utcnow().strftime("%Y%m%d"))
        base = Path(self.config.get("equity_research_results_dir", "")) or Path(
            os.path.join(os.path.expanduser("~"), ".tradingagents", "equity_research")
        )
        log_dir = base / ticker / str(report_id)
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"full_states_log_{datetime.utcnow().strftime('%Y-%m-%d')}.json"
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("Failed to save state log: %s", exc)

    def _create_tool_nodes(self) -> dict[str, ToolNode]:
        """Create tool nodes for the graph."""
        return {}
