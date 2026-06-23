"""Main orchestrator for Deep Equity Research workflow."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from langgraph.prebuilt import ToolNode

from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.graph.propagation import EquityPropagator
from tradingagents.equity_research.graph.setup import EquityGraphSetup
from tradingagents.equity_research.storage.db import init_db
from tradingagents.llm_clients import create_llm_client

logger = logging.getLogger(__name__)


class EquityResearchGraph:
    """Hypothesis-driven equity research workflow (MVP1)."""

    def __init__(
        self,
        debug: bool = False,
        config: dict[str, Any] | None = None,
        callbacks: list | None = None,
        init_database: bool = True,
    ):
        self.debug = debug
        self.config = config or DEFAULT_CONFIG.copy()
        self.callbacks = callbacks or []
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

        self.deps = EquityResearchDeps(
            config=self.config,
            deep_llm=deep_client.get_llm(),
            quick_llm=quick_client.get_llm()
        )
        self.propagator = EquityPropagator(
            max_recur_limit=self.config.get("equity_research", {}).get("max_recur_limit", 100),
        )
        workflow = EquityGraphSetup(self.deps).setup_graph()
        self.graph = workflow.compile()
        self.curr_state = None
        self.ticker = None

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

        # Sampling temperature is cross-provider: forward it whenever set.
        # float() here so a value coming from a TRADINGAGENTS_TEMPERATURE env
        # string ("0.2") works the same as a programmatic float.
        temperature = self.config.get("temperature")
        if temperature is not None and temperature != "":
            kwargs["temperature"] = float(temperature)

        return kwargs

    def propagate(self, ticker: str, trade_date: str, **kwargs: Any) -> tuple[dict[str, Any], str]:
        """Run full equity research pipeline for a ticker."""
        self.ticker = ticker.upper()
        init_state = self.propagator.create_initial_state(self.ticker, trade_date=trade_date, **kwargs)
        args = self.propagator.get_graph_args(self.callbacks)

        if self.debug:
            final_state = None
            for state in self.graph.stream(init_state, **args):
                final_state = state
                node = list(state.keys())[-1] if isinstance(state, dict) else None
                logger.debug("Equity research node update: %s", node)
        else:
            final_state = self.graph.invoke(init_state, **args)

        self.curr_state = final_state
        self._save_state_log(final_state)
        summary = final_state.get("final_report", "")[:500] if final_state else ""
        return final_state, summary

    def _save_state_log(self, state: dict[str, Any]) -> None:
        if not state:
            return
        ticker = state.get("ticker", "UNKNOWN")
        report_id = state.get("report_id", datetime.utcnow().strftime("%Y%m%d"))
        base = Path(self.config.get("equity_research_results_dir", "")) or Path(
            os.path.join(os.path.expanduser("~"), ".tradingagents", "equity_research")
        )
        log_dir = base / ticker / report_id
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"full_states_log_{datetime.utcnow().strftime('%Y-%m-%d')}.json"
        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except Exception as exc:
            logger.warning("Failed to save state log: %s", exc)

    def _create_tool_nodes(self) -> dict[str, ToolNode]:
        """Create tool nodes for the graph."""
        # Placeholder for any future tool nodes (e.g., data retrieval, charting)
        return {}