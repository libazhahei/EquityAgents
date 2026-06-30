"""Generic research subgraph builder."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.nodes.executor import (
    create_executor_apply_node,
    create_executor_dispatch_node,
    create_executor_tools_node,
    executor_router,
)
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
        self.tool_nodes_by_caller = self._init_tool_nodes_by_caller()
        self.executor_tool_nodes = self.tool_nodes_for("executor")
        self.executor_tool_node_name = self.preferred_tool_node_name("executor")

    def _init_tool_nodes_by_caller(self) -> dict[str, dict[str, Any]]:
        """Prebuild tool nodes grouped by caller node name."""
        base = create_executor_tools_node(self.deps)
        callers = (
            "executor",
            "initial_planner",
            "loop_planner",
            "synthesizer",
            "reflector",
            "finalizer",
        )
        by_caller: dict[str, dict[str, Any]] = {}
        for caller in callers:
            by_caller[caller] = {
                f"{caller}_tools": base,
                f"{caller}_tools_{self.tp.task_id}": base,
            }
        return by_caller

    def tool_nodes_for(self, caller_name: str) -> dict[str, Any]:
        return self.tool_nodes_by_caller.get(caller_name, {})

    def preferred_tool_node_name(self, caller_name: str) -> str:
        by_caller = self.tp.extra_config.get("tool_node_name_by_caller", {})
        if caller_name in by_caller:
            return str(by_caller[caller_name])
        return f"{caller_name}_tools_{self.tp.task_id}"

    def all_tool_nodes(self) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        for mapping in self.tool_nodes_by_caller.values():
            merged.update(mapping)
        return merged

    def build(self) -> StateGraph:
        graph = StateGraph(AgentState)
        tp = self.tp

        graph.add_node("skill_selector_agent", create_skill_selector_agent(self.deps, tp))
        graph.add_node("skill_tools", create_skill_tools_node(self.deps, tp))
        graph.add_node("skill_context_apply", create_skill_context_apply(self.deps, tp))
        graph.add_node("initial_planner", create_planner_node(self.deps, tp, mode="initial"))
        graph.add_node(
            "executor",
            create_executor_dispatch_node(
                self.deps,
                tp,
                tool_node_name=self.executor_tool_node_name,
            ),
        )
        for node_name, tool_node in self.all_tool_nodes().items():
            graph.add_node(node_name, tool_node)
        graph.add_node("executor_apply", create_executor_apply_node(self.deps, tp))
        graph.add_node("synthesizer", create_synthesizer_node(self.deps, tp))
        graph.add_node("reflector", create_reflector_node(self.deps, tp))
        graph.add_node("loop_planner", create_planner_node(self.deps, tp, mode="loop"))
        graph.add_node("finalizer", create_finalizer_node(self.deps, tp))

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
        graph.add_conditional_edges(
            "executor",
            executor_router,
            {
                "apply": "executor_apply",
                **{name: name for name in self.executor_tool_nodes},
            },
        )
        for node_name in self.executor_tool_nodes:
            graph.add_edge(node_name, "executor_apply")
        graph.add_edge("executor_apply", "synthesizer")
        graph.add_edge("synthesizer", "reflector")
        graph.add_conditional_edges(
            "reflector",
            coverage_reflector_router,
            {
                "exit": "finalizer",
                "run_existing_queue": "executor",
                "plan_more": "loop_planner",
            },
        )
        graph.add_conditional_edges(
            "loop_planner",
            loop_planner_router,
            {
                "run": "executor",
                "exit": "finalizer",
            },
        )

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
