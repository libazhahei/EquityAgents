"""Section question tree planner LangGraph subgraph."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.section_planner.nodes import (
    create_background_extractor_node,
    create_coverage_validator_node,
    create_finalize_plan_node,
    create_grounding_apply_node,
    create_grounding_dispatch_node,
    create_grounding_tools_node,
    create_question_tree_generator_node,
    create_template_interpreter_node,
    grounding_router,
)
from tradingagents.equity_research.agents.section_planner.state import SectionPlannerState


class SectionPlannerSubgraph:
    def __init__(self, deps: EquityResearchDeps) -> None:
        self.deps = deps

    def build(self) -> StateGraph:
        graph = StateGraph(SectionPlannerState)

        graph.add_node("template_interpreter", create_template_interpreter_node(self.deps))
        graph.add_node("background_extractor", create_background_extractor_node(self.deps))
        graph.add_node("grounding_dispatch", create_grounding_dispatch_node(self.deps))
        graph.add_node("grounding_tools", create_grounding_tools_node())
        graph.add_node("grounding_apply", create_grounding_apply_node(self.deps))
        graph.add_node("question_tree_generator", create_question_tree_generator_node(self.deps))
        graph.add_node("coverage_validator", create_coverage_validator_node(self.deps))
        graph.add_node("finalize_plan", create_finalize_plan_node(self.deps))

        graph.set_entry_point("template_interpreter")
        graph.add_edge("template_interpreter", "background_extractor")
        graph.add_conditional_edges(
            "background_extractor",
            grounding_router,
            {
                "grounding_dispatch": "grounding_dispatch",
                "question_tree_generator": "question_tree_generator",
            },
        )
        graph.add_edge("grounding_dispatch", "grounding_tools")
        graph.add_edge("grounding_tools", "grounding_apply")
        graph.add_edge("grounding_apply", "question_tree_generator")
        graph.add_edge("question_tree_generator", "coverage_validator")
        graph.add_edge("coverage_validator", "finalize_plan")
        graph.add_edge("finalize_plan", END)

        return graph

    def compile(self, *, checkpointer=None):
        return self.build().compile(checkpointer=checkpointer)


def create_run_section_planner_subgraph(deps: EquityResearchDeps):
    compiled = SectionPlannerSubgraph(deps).compile()

    def run_section_planner(state: dict) -> dict:
        from tradingagents.equity_research.agents.section_planner.state import empty_section_planner_state

        subgraph_input = empty_section_planner_state(state)
        result = compiled.invoke(subgraph_input)
        return result

    return run_section_planner
