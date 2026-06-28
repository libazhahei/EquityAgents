"""Minimal LangGraph for manual consensus testing."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from tradingagents.equity_research.agents.consensus.subgraph import create_run_consensus_subgraph
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.state import AgentState, empty_agent_state
from tradingagents.equity_research.state.consensus_schemas import empty_structured_consensus_view
from tradingagents.equity_research.tasks.consensus.profile import CONSENSUS_TASK_PROFILE


def create_initialize_demo_state(
    *,
    ticker: str,
    sector: str = "",
    max_iterations: int = 5,
    report_type: str = "initiation",
):
    def initialize_demo_state(state: AgentState) -> dict[str, Any]:
        base = empty_agent_state(
            {
                "ticker": ticker,
                "sector": sector,
                "report_type": report_type,
                "documents": [],
                "api_calls": 0,
                "errors": [],
            },
            task_profile=CONSENSUS_TASK_PROFILE.to_dict(),
            max_iterations=max_iterations,
        )
        base["structured_view"] = empty_structured_consensus_view(ticker).model_dump()
        return base

    return initialize_demo_state


class ConsensusDemoGraph:
    """initialize → run_consensus → END"""

    def __init__(self, deps: EquityResearchDeps, *, ticker: str, sector: str = "", max_iterations: int = 5):
        self.deps = deps
        self.ticker = ticker
        self.sector = sector
        self.max_iterations = max_iterations
        self._run_consensus = create_run_consensus_subgraph(deps)

    def build(self) -> StateGraph:
        g = StateGraph(dict)
        g.add_node(
            "initialize_demo_state",
            create_initialize_demo_state(
                ticker=self.ticker,
                sector=self.sector,
                max_iterations=self.max_iterations,
            ),
        )

        run_fn = self._run_consensus

        def run_consensus_subgraph(state: dict[str, Any]) -> dict[str, Any]:
            parent = {
                "ticker": state.get("ticker", self.ticker),
                "sector": state.get("sector", self.sector),
                "report_type": state.get("report_type", "initiation"),
                "documents": state.get("documents", []),
                "api_calls": state.get("api_calls", 0),
                "errors": state.get("errors", []),
                "max_consensus_iterations": state.get("max_iterations", self.max_iterations),
                "consensus_search_memory": state.get("search_memory", []),
            }
            result = run_fn(parent)
            return {
                **state,
                "structured_view": result.get("consensus_view", {}),
                "final_report": result.get("consensus_report", ""),
                "assumptions": result.get("consensus_assumptions", {}),
                "iterations": result.get("consensus_iterations", 0),
                "search_memory": result.get("consensus_search_memory", []),
                "evidence_buffer": result.get("consensus_evidence_buffer", []),
                "documents": result.get("documents", []),
                "api_calls": result.get("api_calls", 0),
                "errors": result.get("errors", []),
                "compliance_flags": result.get("compliance_flags", []),
            }

        g.add_node("run_consensus_subgraph", run_consensus_subgraph)
        g.add_edge(START, "initialize_demo_state")
        g.add_edge("initialize_demo_state", "run_consensus_subgraph")
        g.add_edge("run_consensus_subgraph", END)
        return g

    def compile(self):
        return self.build().compile()

    def invoke(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.compile().invoke({}, config=config or {})
