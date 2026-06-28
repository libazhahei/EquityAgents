"""Consensus subgraph builder and parent-state wrapper."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph

from tradingagents.equity_research.agents.consensus.nodes import (
    create_assumption_batch_executor,
    create_assumption_compliance_check,
    create_assumption_probe_gate,
    create_assumption_query_planner,
    create_assumption_synthesizer,
    create_consensus_skill_context_apply,
    create_consensus_skill_selector_agent,
    create_consensus_skill_tools,
    create_consensus_synthesizer,
    create_coverage_reflector,
    create_finalizer,
    create_human_review,
    create_loop_query_planner,
    create_initial_query_planner,
    create_query_batch_executor,
)
from tradingagents.equity_research.agents.consensus.routers import (
    assumption_probe_gate_router,
    coverage_reflector_router,
    gap_query_planner_router,
    human_review_router,
    skill_selector_router,
)
from tradingagents.equity_research.agents.consensus.state import (
    ConsensusSubgraphState,
    empty_consensus_subgraph_state,
)
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.consensus_schemas import empty_structured_consensus_view


def _human_review_config(deps: EquityResearchDeps) -> dict[str, Any]:
    er = deps.config.get("equity_research", {})
    defaults = {"enabled": False, "interrupt": False}
    return {**defaults, **(er.get("consensus_human_review") or {})}


class ConsensusSubgraph:
    def __init__(self, deps: EquityResearchDeps) -> None:
        self.deps = deps

    def build(self) -> StateGraph:
        graph = StateGraph(ConsensusSubgraphState)

        graph.add_node("skill_selector_agent", create_consensus_skill_selector_agent(self.deps))
        graph.add_node("skill_tools", create_consensus_skill_tools(self.deps))
        graph.add_node("skill_context_apply", create_consensus_skill_context_apply(self.deps))
        graph.add_node("initial_query_planner", create_initial_query_planner(self.deps))
        graph.add_node("query_batch_executor", create_query_batch_executor(self.deps))
        graph.add_node("consensus_synthesizer", create_consensus_synthesizer(self.deps))
        graph.add_node("coverage_reflector", create_coverage_reflector(self.deps))
        graph.add_node("gap_query_planner", create_loop_query_planner(self.deps))
        graph.add_node("assumption_probe_gate", create_assumption_probe_gate(self.deps))
        graph.add_node("assumption_query_planner", create_assumption_query_planner(self.deps))
        graph.add_node("assumption_batch_executor", create_assumption_batch_executor(self.deps))
        graph.add_node("assumption_synthesizer", create_assumption_synthesizer(self.deps))
        graph.add_node("assumption_compliance_check", create_assumption_compliance_check(self.deps))
        graph.add_node("finalizer", create_finalizer(self.deps))
        graph.add_node("human_review", create_human_review(self.deps))

        graph.add_edge(START, "skill_selector_agent")
        graph.add_conditional_edges(
            "skill_selector_agent",
            skill_selector_router,
            {
                "tools": "skill_tools",
                "apply": "skill_context_apply",
            },
        )
        graph.add_edge("skill_tools", "skill_context_apply")
        graph.add_edge("skill_context_apply", "initial_query_planner")
        graph.add_edge("initial_query_planner", "query_batch_executor")
        graph.add_edge("query_batch_executor", "consensus_synthesizer")
        graph.add_edge("consensus_synthesizer", "coverage_reflector")
        graph.add_conditional_edges(
            "coverage_reflector",
            coverage_reflector_router,
            {
                "exit": "assumption_probe_gate",
                "run_existing_queue": "query_batch_executor",
                "plan_more": "gap_query_planner",
            },
        )
        graph.add_conditional_edges(
            "gap_query_planner",
            gap_query_planner_router,
            {
                "run": "query_batch_executor",
                "exit": "assumption_probe_gate",
            },
        )
        graph.add_conditional_edges(
            "assumption_probe_gate",
            assumption_probe_gate_router,
            {
                "probe": "assumption_query_planner",
                "done": "finalizer",
            },
        )
        graph.add_edge("assumption_query_planner", "assumption_batch_executor")
        graph.add_edge("assumption_batch_executor", "assumption_synthesizer")
        graph.add_edge("assumption_synthesizer", "assumption_compliance_check")
        graph.add_edge("assumption_compliance_check", "finalizer")
        graph.add_edge("finalizer", "human_review")
        graph.add_conditional_edges(
            "human_review",
            human_review_router,
            {
                "replan": "gap_query_planner",
                "done": END,
            },
        )
        return graph

    def compile(self, *, checkpointer=None, human_review_config: dict[str, Any] | None = None):
        config = human_review_config or _human_review_config(self.deps)
        graph = self.build()
        if config.get("interrupt"):
            if checkpointer is None:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
            return graph.compile(
                checkpointer=checkpointer,
                interrupt_before=["human_review"],
            )
        return graph.compile()


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
        max_iter = int(state.get("max_consensus_iterations", 5))
        subgraph_input = empty_consensus_subgraph_state(state, max_iterations=max_iter)
        ticker = state.get("ticker", "")
        if not subgraph_input.get("consensus_view"):
            subgraph_input["consensus_view"] = empty_structured_consensus_view(ticker).model_dump()
        if state.get("human_followup_query"):
            subgraph_input["human_followup_query"] = state["human_followup_query"]

        result = compiled.invoke(subgraph_input)

        consensus_view = result.get("consensus_view") or empty_structured_consensus_view(ticker).model_dump()
        updates: dict[str, Any] = {
            "consensus_view": consensus_view,
            "consensus_report": result.get("consensus_report", ""),
            "consensus_assumptions": result.get("consensus_assumptions", {}),
            "consensus_evidence_buffer": result.get("evidence_buffer", []),
            "consensus_search_memory": result.get("search_memory", []),
            "consensus_iterations": result.get("consensus_iterations", 0),
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
            "iterations": result.get("consensus_iterations", 0),
            "evidence_count": len(result.get("evidence_buffer", [])),
        }))
        return updates

    return run_consensus_subgraph
