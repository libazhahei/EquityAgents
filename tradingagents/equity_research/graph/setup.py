"""LangGraph setup for Equity R&D-Agent parent spine.

Current spine (research MVP):
  initialize → consensus → assumption → human_review_1 → planner →
  human_review_2 → pick_next_section ⇄ section_research → END

Modeling / writing node factories remain available for later rewiring but are
not attached to this graph.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.dynamic_planning import create_dynamic_planning
from tradingagents.equity_research.agents.init_agents import create_initialize_state
from tradingagents.equity_research.graph.human_review import (
    create_human_review_1,
    create_human_review_2,
    create_pick_next_section,
)
from tradingagents.equity_research.graph.nested import (
    make_nested_assumption_node,
    make_nested_consensus_node,
    make_nested_section_research_node,
)
from tradingagents.equity_research.graph.routers import section_loop_router
from tradingagents.equity_research.state.equity_research_state import EquityResearchState


def _wrap_with_progress(deps: EquityResearchDeps, stage: str, node_fn):
    def wrapped(state: dict[str, Any]) -> dict[str, Any]:
        bus = getattr(deps, "progress_bus", None)
        if bus is not None:
            bus.emit(
                stage=stage,
                node=stage,
                status="started",
                run_id=str(state.get("run_id", "")),
                thread_id=str(state.get("_thread_id", "")),
                ticker=str(state.get("ticker", "")),
            )
        try:
            updates = node_fn(state)
            if bus is not None:
                bus.emit(
                    stage=stage,
                    node=stage,
                    status="succeeded",
                    run_id=str(state.get("run_id", "")),
                    thread_id=str(state.get("_thread_id", "")),
                    ticker=str(state.get("ticker", "")),
                )
            return updates
        except Exception as exc:
            if bus is not None:
                bus.emit(
                    stage=stage,
                    node=stage,
                    status="failed",
                    run_id=str(state.get("run_id", "")),
                    thread_id=str(state.get("_thread_id", "")),
                    ticker=str(state.get("ticker", "")),
                    payload={"error": str(exc)},
                )
            raise

    return wrapped


class EquityGraphSetup:
    def __init__(
        self,
        deps: EquityResearchDeps,
        *,
        checkpointer: Any = None,
    ):
        self.deps = deps
        self.checkpointer = checkpointer

    def setup_graph(self) -> StateGraph:
        g = StateGraph(EquityResearchState)
        cp = self.checkpointer

        g.add_node("initialize_state", create_initialize_state(self.deps))
        g.add_node("consensus", make_nested_consensus_node(self.deps, checkpointer=cp))
        g.add_node("assumption", make_nested_assumption_node(self.deps, checkpointer=cp))
        g.add_node("human_review_1", create_human_review_1(self.deps))
        g.add_node(
            "planner",
            _wrap_with_progress(self.deps, "planner", create_dynamic_planning(self.deps)),
        )
        g.add_node("human_review_2", create_human_review_2(self.deps))
        g.add_node("pick_next_section", create_pick_next_section(self.deps))
        g.add_node(
            "section_research",
            make_nested_section_research_node(self.deps, checkpointer=cp),
        )

        g.set_entry_point("initialize_state")
        g.add_edge("initialize_state", "consensus")
        g.add_edge("consensus", "assumption")
        g.add_edge("assumption", "human_review_1")
        g.add_edge("human_review_1", "planner")
        g.add_edge("planner", "human_review_2")
        g.add_edge("human_review_2", "pick_next_section")
        g.add_conditional_edges(
            "pick_next_section",
            section_loop_router,
            {
                "section_research": "section_research",
                "end": END,
            },
        )
        g.add_edge("section_research", "pick_next_section")
        return g
