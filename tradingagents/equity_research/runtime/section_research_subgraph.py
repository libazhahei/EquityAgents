"""Section research subgraph — extends GenericResearchSubgraph."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.nodes.executor import create_executor_tools_node
from tradingagents.equity_research.runtime.nodes.finalizer import create_finalizer_node
from tradingagents.equity_research.runtime.nodes.section_executor import (
    build_section_executor_tool_set_nodes,
    create_section_executor_apply_node,
    create_section_executor_dispatch_node,
    section_executor_router,
)
from tradingagents.equity_research.runtime.nodes.section_planner import (
    create_section_planner_node,
    section_initial_planner_router,
)
from tradingagents.equity_research.runtime.nodes.section_reflector import (
    create_section_reflector_node,
    section_loop_planner_router,
    section_reflector_router,
)
from tradingagents.equity_research.runtime.nodes.skill_selector import (
    create_skill_context_apply,
    create_skill_selector_agent,
    create_skill_tools_node,
)
from tradingagents.equity_research.runtime.nodes.synthesizer import create_synthesizer_node
from tradingagents.equity_research.runtime.nodes.tool_router import (
    create_executor_tool_router_node,
    executor_tool_group_router,
)
from tradingagents.equity_research.runtime.routers import skill_selector_router
from tradingagents.equity_research.runtime.state import AgentState
from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph, _human_review_config
from tradingagents.equity_research.runtime.task_profile import TaskProfile


class SectionResearchSubgraph(GenericResearchSubgraph):
    """PER subgraph with multi-step research plans and ReAct executor."""

    def _init_tool_nodes_by_caller(self) -> dict[str, dict[str, Any]]:
        executor_sets = build_section_executor_tool_set_nodes(self.deps, self.tp)
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
            if caller == "executor":
                by_caller[caller] = dict(executor_sets)
            else:
                generic = create_executor_tools_node(self.deps)
                by_caller[caller] = {
                    f"{caller}_tools": generic,
                    f"{caller}_tools_{self.tp.task_id}": generic,
                }
        return by_caller

    def build(self) -> StateGraph:
        graph = StateGraph(AgentState)
        tp = self.tp

        graph.add_node("skill_selector_agent", create_skill_selector_agent(self.deps, tp))
        graph.add_node("skill_tools", create_skill_tools_node(self.deps, tp))
        graph.add_node("skill_context_apply", create_skill_context_apply(self.deps, tp))
        graph.add_node("initial_planner", create_section_planner_node(self.deps, tp, mode="initial"))
        graph.add_node("executor", create_section_executor_dispatch_node(self.deps, tp))
        for node_name, tool_node in self.all_tool_nodes().items():
            graph.add_node(node_name, tool_node)
        graph.add_node("executor_tool_router", create_executor_tool_router_node())
        graph.add_node("executor_apply", create_section_executor_apply_node(self.deps, tp))
        graph.add_node("synthesizer", create_synthesizer_node(self.deps, tp))
        graph.add_node("reflector", create_section_reflector_node(self.deps, tp))
        graph.add_node("loop_planner", create_section_planner_node(self.deps, tp, mode="loop"))
        graph.add_node("finalizer", create_finalizer_node(self.deps, tp))

        graph.add_edge(START, "skill_selector_agent")
        graph.add_conditional_edges(
            "skill_selector_agent",
            skill_selector_router,
            {"tools": "skill_tools", "apply": "skill_context_apply"},
        )
        graph.add_edge("skill_tools", "skill_context_apply")
        graph.add_edge("skill_context_apply", "initial_planner")
        graph.add_conditional_edges(
            "initial_planner",
            section_initial_planner_router,
            {
                "executor": "executor",
                "loop_planner": "loop_planner",
            },
        )
        graph.add_conditional_edges(
            "executor",
            section_executor_router,
            {
                "apply": "executor_apply",
                "continue": "executor",
                "tool_router": "executor_tool_router",
            },
        )
        graph.add_conditional_edges(
            "executor_tool_router",
            executor_tool_group_router,
            {name: name for name in self.executor_tool_nodes},
        )
        for node_name in self.executor_tool_nodes:
            graph.add_edge(node_name, "executor")
        graph.add_edge("executor_apply", "synthesizer")
        graph.add_edge("synthesizer", "reflector")
        graph.add_conditional_edges(
            "reflector",
            section_reflector_router,
            {
                "exit": "finalizer",
                "run_existing_queue": "executor",
                "plan_more": "loop_planner",
                "needs_human": "finalizer",
            },
        )
        graph.add_conditional_edges(
            "loop_planner",
            section_loop_planner_router,
            {
                "run": "executor",
                "exit": "finalizer",
            },
        )
        graph.add_edge("finalizer", END)
        return graph

    def compile(self, *, checkpointer=None, human_review_config: dict[str, Any] | None = None):
        config = human_review_config or _human_review_config(self.deps, self.tp)
        return self.build().compile()
