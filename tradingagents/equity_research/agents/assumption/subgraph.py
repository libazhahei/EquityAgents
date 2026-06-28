"""Assumption subgraph wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.state import empty_agent_state
from tradingagents.equity_research.runtime.subgraph_runner import create_run_profile_subgraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tasks.assumption.profile import ASSUMPTION_TASK_PROFILE
from tradingagents.equity_research.tasks.assumption.schemas import AssumptionView, empty_assumption_view


def _seed_assumption_state(parent: dict[str, Any], profile: TaskProfile) -> dict[str, Any]:
    ticker = parent.get("ticker", "")
    max_iter = int(parent.get("max_assumption_iterations", profile.max_iterations))
    subgraph_input = empty_agent_state(
        parent,
        task_profile=profile.to_dict(),
        max_iterations=max_iter,
    )
    subgraph_input["structured_view"] = empty_assumption_view(ticker).model_dump()
    subgraph_input["search_memory"] = list(parent.get("consensus_search_memory", []))
    subgraph_input["evidence_buffer"] = list(parent.get("consensus_evidence_buffer", []))
    subgraph_input["parent_context"] = {
        **dict(parent.get("parent_context", {})),
        "consensus_view": parent.get("consensus_view", {}),
        "consensus_report": parent.get("consensus_report", ""),
    }
    if parent.get("human_followup_query"):
        subgraph_input["human_followup_query"] = parent["human_followup_query"]
    return subgraph_input


def _map_assumption_result(
    deps: EquityResearchDeps,
    parent: dict[str, Any],
    result: dict[str, Any],
    profile: TaskProfile,
) -> dict[str, Any]:
    view_raw = result.get("structured_view") or empty_assumption_view(parent.get("ticker", "")).model_dump()
    assumptions: dict[str, Any] = {}
    suggestions: list[dict] = []
    directions: list[str] = []
    try:
        view = AssumptionView.model_validate(view_raw)
        assumptions = view.current_assumptions.model_dump()
        suggestions = [s.model_dump() for s in view.research_suggestions]
        directions = list(view.research_directions)
    except Exception:
        if isinstance(view_raw, dict):
            assumptions = view_raw.get("current_assumptions", {})
            suggestions = view_raw.get("research_suggestions", [])
            directions = view_raw.get("research_directions", [])

    updates: dict[str, Any] = {
        "assumption_view": view_raw,
        "consensus_assumptions": assumptions,
        "research_suggestions": suggestions,
        "research_directions": directions,
        "assumption_report": result.get("final_report", ""),
        "assumption_search_memory": result.get("search_memory", []),
        "assumption_evidence_buffer": result.get("evidence_buffer", []),
        "documents": result.get("documents", parent.get("documents", [])),
        "api_calls": result.get("api_calls", parent.get("api_calls", 0)),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    if result.get("compliance_flags"):
        flags = list(parent.get("compliance_flags", []))
        flags.extend(result["compliance_flags"])
        updates["compliance_flags"] = flags
    if result.get("errors"):
        errors = list(parent.get("errors", []))
        errors.extend(result["errors"])
        updates["errors"] = errors
    if result.get("research_traces"):
        updates["research_traces"] = result["research_traces"]
    updates.update(deps.trace({**parent, **updates}, "assumption_subgraph", {
        "iterations": result.get("iterations", 0),
        "evidence_count": len(result.get("evidence_buffer", [])),
        "suggestions": len(suggestions),
    }))
    return updates


def create_run_assumption_subgraph(deps: EquityResearchDeps, *, checkpointer=None):
    return create_run_profile_subgraph(
        deps,
        ASSUMPTION_TASK_PROFILE,
        seed_state=_seed_assumption_state,
        map_result=lambda parent, result, profile: _map_assumption_result(deps, parent, result, profile),
        checkpointer=checkpointer,
    )
