"""Nested subgraph node adapters for the equity research parent graph."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from langchain_core.runnables import RunnableConfig

from tradingagents.equity_research.agents.assumption.subgraph import (
    _map_assumption_result,
    _seed_assumption_state,
)
from tradingagents.equity_research.agents.consensus.subgraph import (
    _map_consensus_result,
    _seed_consensus_state,
)
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.research_loop.subgraph import (
    _map_section_research_result,
    _pick_section_id,
)
from tradingagents.equity_research.graph.checkpointer import upsert_run_edge
from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tasks.assumption.profile import ASSUMPTION_TASK_PROFILE
from tradingagents.equity_research.tasks.consensus.profile import CONSENSUS_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.profile import SECTION_RESEARCH_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.seed import seed_section_research_state

# Parent-path consensus never interrupts inside the subgraph.
_BYPASS_CONSENSUS_HR = {"enabled": False, "interrupt": False}


def _emit(
    deps: EquityResearchDeps,
    *,
    stage: str,
    node: str,
    status: str,
    state: dict[str, Any],
    section_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    bus = getattr(deps, "progress_bus", None)
    if bus is None:
        return
    bus.emit(
        stage=stage,
        node=node,
        status=status,
        run_id=str(state.get("run_id", "")),
        thread_id=str(state.get("_thread_id", "")),
        ticker=str(state.get("ticker", "")),
        section_id=section_id,
        payload=payload or {},
    )


def _maybe_upsert_edge(
    checkpointer: Any,
    state: dict[str, Any],
    *,
    node_path: str,
    status: str,
    section_id: str | None = None,
) -> None:
    if checkpointer is None:
        return
    run_id = state.get("run_id")
    ticker = state.get("ticker")
    as_of = state.get("trade_date") or state.get("as_of_date") or ""
    if not run_id or not ticker:
        return
    try:
        upsert_run_edge(
            checkpointer,
            run_id=str(run_id),
            ticker=str(ticker),
            as_of_date=str(as_of),
            node_path=node_path,
            section_id=section_id,
            status=status,
        )
    except Exception:
        pass


def make_nested_profile_node(
    deps: EquityResearchDeps,
    profile: TaskProfile,
    *,
    seed_state: Callable[[dict[str, Any], TaskProfile], Any],
    map_result: Callable[[dict[str, Any], dict[str, Any], TaskProfile], dict[str, Any]],
    checkpointer=None,
    human_review_config: dict[str, Any] | None = None,
    stage: str | None = None,
):
    """Compile a GenericResearchSubgraph and expose it as a parent node."""
    compiled = GenericResearchSubgraph(deps, profile).compile(
        checkpointer=checkpointer,
        human_review_config=human_review_config,
    )
    stage_name = stage or profile.task_id
    node_name = stage_name

    def node(state: dict[str, Any], config: RunnableConfig | None = None) -> dict[str, Any]:
        cfg = config or {}
        _emit(deps, stage=stage_name, node=node_name, status="started", state=state)
        _maybe_upsert_edge(checkpointer, state, node_path=stage_name, status="running")
        try:
            child_input = seed_state(state, profile)
            result = compiled.invoke(child_input, cfg)
            updates = map_result(state, result, profile)
            _emit(deps, stage=stage_name, node=node_name, status="succeeded", state={**state, **updates})
            _maybe_upsert_edge(checkpointer, state, node_path=stage_name, status="succeeded")
            return updates
        except Exception as exc:
            _emit(
                deps,
                stage=stage_name,
                node=node_name,
                status="failed",
                state=state,
                payload={"error": str(exc)},
            )
            _maybe_upsert_edge(
                checkpointer,
                state,
                node_path=stage_name,
                status="failed",
                section_id=None,
            )
            raise

    return node


def make_nested_consensus_node(deps: EquityResearchDeps, *, checkpointer=None):
    return make_nested_profile_node(
        deps,
        CONSENSUS_TASK_PROFILE,
        seed_state=_seed_consensus_state,
        map_result=lambda parent, result, profile: _map_consensus_result(
            deps, parent, result, profile
        ),
        checkpointer=checkpointer,
        human_review_config=_BYPASS_CONSENSUS_HR,
        stage="consensus",
    )


def make_nested_assumption_node(deps: EquityResearchDeps, *, checkpointer=None):
    return make_nested_profile_node(
        deps,
        ASSUMPTION_TASK_PROFILE,
        seed_state=_seed_assumption_state,
        map_result=lambda parent, result, profile: _map_assumption_result(
            deps, parent, result, profile
        ),
        checkpointer=checkpointer,
        human_review_config={"enabled": False, "interrupt": False},
        stage="assumption",
    )


def make_nested_section_research_node(deps: EquityResearchDeps, *, checkpointer=None):
    """Section research nested node; picks active/selected section then maps back."""
    tp = SECTION_RESEARCH_TASK_PROFILE
    compiled = SectionResearchSubgraph(deps, tp).compile(checkpointer=checkpointer)

    def node(state: dict[str, Any], config: RunnableConfig | None = None) -> dict[str, Any]:
        cfg = dict(config or {})
        er = deps.config.get("equity_research", {})
        recursion_limit = int(
            er.get("section_research_recursion_limit", er.get("max_recur_limit", 200))
        )
        configurable = dict(cfg.get("configurable") or {})
        cfg["configurable"] = configurable
        cfg["recursion_limit"] = recursion_limit

        section_id = _pick_section_id(state)
        node_path = f"section_research/{section_id}"
        _emit(
            deps,
            stage="section_research",
            node="section_research",
            status="started",
            state=state,
            section_id=section_id,
        )
        _maybe_upsert_edge(
            checkpointer,
            state,
            node_path=node_path,
            status="running",
            section_id=section_id,
        )
        try:
            section_plan = (state.get("section_plans") or {}).get(section_id, {})
            seeded_parent = {**state, "_section_research_recursion_limit": recursion_limit}
            subgraph_input = seed_section_research_state(
                seeded_parent,
                tp,
                section_id=section_id,
                section_plan=section_plan,
            )
            result = compiled.invoke(subgraph_input, cfg)
            updates = _map_section_research_result(
                deps, seeded_parent, result, tp, section_id=section_id,
            )
            _emit(
                deps,
                stage="section_research",
                node="section_research",
                status="succeeded",
                state={**state, **updates},
                section_id=section_id,
            )
            _maybe_upsert_edge(
                checkpointer,
                state,
                node_path=node_path,
                status="succeeded",
                section_id=section_id,
            )
            return updates
        except Exception as exc:
            _emit(
                deps,
                stage="section_research",
                node="section_research",
                status="failed",
                state=state,
                section_id=section_id,
                payload={"error": str(exc)},
            )
            _maybe_upsert_edge(
                checkpointer,
                state,
                node_path=node_path,
                status="failed",
                section_id=section_id,
            )
            raise

    return node
