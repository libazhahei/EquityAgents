"""Generic research subgraph builder."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.nodes.assumption_probe import (
    create_assumption_batch_executor,
    create_assumption_compliance_check,
    create_assumption_probe_gate,
    create_assumption_query_planner,
    create_assumption_synthesizer,
)
from tradingagents.equity_research.runtime.nodes.executor import create_executor_node
from tradingagents.equity_research.runtime.nodes.finalizer import create_finalizer_node
from tradingagents.equity_research.runtime.nodes.human_review import create_human_review_node
from tradingagents.equity_research.runtime.nodes.planner import create_planner_node
from tradingagents.equity_research.runtime.nodes.reflector import create_reflector_node
from tradingagents.equity_research.runtime.nodes.skill_selector import (
    create_skill_context_apply,
    create_skill_selector_agent,
    create_skill_tools_node,
)
from tradingagents.equity_research.runtime.nodes.synthesizer import create_synthesizer_node
from tradingagents.equity_research.runtime.routers import (
    assumption_probe_gate_router,
    coverage_reflector_router,
    human_review_router,
    loop_planner_router,
    skill_selector_router,
)
from tradingagents.equity_research.runtime.state import AgentState
from tradingagents.equity_research.runtime.task_profile import TaskProfile


def _human_review_config(deps: EquityResearchDeps, task_profile: TaskProfile) -> dict[str, Any]:
    er = deps.config.get("equity_research", {})
    defaults = {"enabled": False, "interrupt": False}
    key = f"{task_profile.task_id}_human_review"
    return {**defaults, **(er.get(key) or er.get("consensus_human_review") or {})}


class GenericResearchSubgraph:
    def __init__(self, deps: EquityResearchDeps, task_profile: TaskProfile) -> None:
        self.deps = deps
        self.tp = task_profile

    def build(self) -> StateGraph:
        graph = StateGraph(AgentState)
        tp = self.tp

        graph.add_node("skill_selector_agent", create_skill_selector_agent(self.deps, tp))
        graph.add_node("skill_tools", create_skill_tools_node(self.deps, tp))
        graph.add_node("skill_context_apply", create_skill_context_apply(self.deps, tp))
        graph.add_node("initial_planner", create_planner_node(self.deps, tp, mode="initial"))
        graph.add_node("executor", create_executor_node(self.deps, tp))
        graph.add_node("synthesizer", create_synthesizer_node(self.deps, tp))
        graph.add_node("reflector", create_reflector_node(self.deps, tp))
        graph.add_node("loop_planner", create_planner_node(self.deps, tp, mode="loop"))
        graph.add_node("finalizer", create_finalizer_node(self.deps, tp))

        if tp.enable_assumption_probe:
            graph.add_node("assumption_probe_gate", create_assumption_probe_gate(self.deps, tp))
            graph.add_node("assumption_query_planner", create_assumption_query_planner(self.deps, tp))
            graph.add_node("assumption_batch_executor", create_assumption_batch_executor(self.deps, tp))
            graph.add_node("assumption_synthesizer", create_assumption_synthesizer(self.deps, tp))
            graph.add_node("assumption_compliance_check", create_assumption_compliance_check(self.deps, tp))

        if tp.enable_human_review:
            graph.add_node("human_review", create_human_review_node(self.deps, tp))

        graph.add_edge(START, "skill_selector_agent")
        graph.add_conditional_edges(
            "skill_selector_agent",
            skill_selector_router,
            {"tools": "skill_tools", "apply": "skill_context_apply"},
        )
        graph.add_edge("skill_tools", "skill_context_apply")
        graph.add_edge("skill_context_apply", "initial_planner")
        graph.add_edge("initial_planner", "executor")
        graph.add_edge("executor", "synthesizer")
        graph.add_edge("synthesizer", "reflector")
        graph.add_conditional_edges(
            "reflector",
            coverage_reflector_router,
            {
                "exit": "assumption_probe_gate" if tp.enable_assumption_probe else "finalizer",
                "run_existing_queue": "executor",
                "plan_more": "loop_planner",
            },
        )
        graph.add_conditional_edges(
            "loop_planner",
            loop_planner_router,
            {
                "run": "executor",
                "exit": "assumption_probe_gate" if tp.enable_assumption_probe else "finalizer",
            },
        )

        if tp.enable_assumption_probe:
            graph.add_conditional_edges(
                "assumption_probe_gate",
                assumption_probe_gate_router,
                {"probe": "assumption_query_planner", "done": "finalizer"},
            )
            graph.add_edge("assumption_query_planner", "assumption_batch_executor")
            graph.add_edge("assumption_batch_executor", "assumption_synthesizer")
            graph.add_edge("assumption_synthesizer", "assumption_compliance_check")
            graph.add_edge("assumption_compliance_check", "finalizer")

        if tp.enable_human_review:
            graph.add_edge("finalizer", "human_review")
            graph.add_conditional_edges(
                "human_review",
                human_review_router,
                {"replan": "loop_planner", "done": END},
            )
        else:
            graph.add_edge("finalizer", END)

        return graph

    def compile(self, *, checkpointer=None, human_review_config: dict[str, Any] | None = None):
        config = human_review_config or _human_review_config(self.deps, self.tp)
        graph = self.build()
        if config.get("interrupt") and self.tp.enable_human_review:
            if checkpointer is None:
                from langgraph.checkpoint.memory import MemorySaver
                checkpointer = MemorySaver()
            return graph.compile(
                checkpointer=checkpointer,
                interrupt_before=["human_review"],
            )
        return graph.compile()
