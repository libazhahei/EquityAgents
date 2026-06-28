"""Consensus subgraph compatibility wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.state import empty_agent_state
from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph
from tradingagents.equity_research.state.consensus_schemas import empty_structured_consensus_view
from tradingagents.equity_research.tasks.consensus.profile import CONSENSUS_TASK_PROFILE


def _human_review_config(deps: EquityResearchDeps) -> dict[str, Any]:
    er = deps.config.get("equity_research", {})
    defaults = {"enabled": False, "interrupt": False}
    return {**defaults, **(er.get("consensus_human_review") or {})}


class ConsensusSubgraph:
    def __init__(self, deps: EquityResearchDeps) -> None:
        self.deps = deps
        self._inner = GenericResearchSubgraph(deps, CONSENSUS_TASK_PROFILE)

    def build(self):
        return self._inner.build()

    def compile(self, *, checkpointer=None, human_review_config: dict[str, Any] | None = None):
        return self._inner.compile(
            checkpointer=checkpointer,
            human_review_config=human_review_config or _human_review_config(self.deps),
        )


def create_run_consensus_subgraph(
    deps: EquityResearchDeps,
    *,
    checkpointer=None,
    human_review_config: dict[str, Any] | None = None,
):
    compiled = ConsensusSubgraph(deps).compile(
        checkpointer=checkpointer,
        human_review_config=human_review_config,
    )

    def run_consensus_subgraph(state: dict[str, Any]) -> dict[str, Any]:
        max_iter = int(state.get("max_consensus_iterations", CONSENSUS_TASK_PROFILE.max_iterations))
        subgraph_input = empty_agent_state(
            state,
            task_profile=CONSENSUS_TASK_PROFILE.to_dict(),
            max_iterations=max_iter,
        )
        ticker = state.get("ticker", "")
        if not subgraph_input.get("structured_view"):
            subgraph_input["structured_view"] = empty_structured_consensus_view(ticker).model_dump()
        if state.get("human_followup_query"):
            subgraph_input["human_followup_query"] = state["human_followup_query"]

        result = compiled.invoke(subgraph_input)

        consensus_view = result.get("structured_view") or empty_structured_consensus_view(ticker).model_dump()
        updates: dict[str, Any] = {
            "consensus_view": consensus_view,
            "consensus_report": result.get("final_report", ""),
            "consensus_assumptions": result.get("assumptions", {}),
            "consensus_evidence_buffer": result.get("evidence_buffer", []),
            "consensus_search_memory": result.get("search_memory", []),
            "consensus_iterations": result.get("iterations", 0),
            "documents": result.get("documents", state.get("documents", [])),
            "api_calls": result.get("api_calls", state.get("api_calls", 0)),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        if result.get("compliance_flags"):
            flags = list(state.get("compliance_flags", []))
            flags.extend(result["compliance_flags"])
            updates["compliance_flags"] = flags
        if result.get("errors"):
            errors = list(state.get("errors", []))
            errors.extend(result["errors"])
            updates["errors"] = errors
        if result.get("research_traces"):
            updates["research_traces"] = result["research_traces"]
        updates.update(deps.trace({**state, **updates}, "consensus_subgraph", {
            "iterations": result.get("iterations", 0),
            "evidence_count": len(result.get("evidence_buffer", [])),
        }))
        return updates

    return run_consensus_subgraph
