"""LangGraph setup for Equity R&D-Agent (~14 outer nodes)."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from tradingagents.equity_research.agents.branch_merge import create_branch_merge
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.dynamic_planning import create_dynamic_planning
from tradingagents.equity_research.agents.final_agents import (
    create_assemble_report,
    create_investment_committee_review,
    create_markdown_memory_export,
)
from tradingagents.equity_research.agents.final_qa import create_final_qa
from tradingagents.equity_research.agents.init_agents import create_initialize_state
from tradingagents.equity_research.agents.modeling_workflow import create_modeling_workflow
from tradingagents.equity_research.agents.research_loop import create_research_loop
from tradingagents.equity_research.agents.risk_mapping import create_risk_mapping
from tradingagents.equity_research.agents.task_analysis import create_analyze_research_task
from tradingagents.equity_research.agents.valuation_workflow import create_valuation_workflow
from tradingagents.equity_research.agents.writing_agents import (
    create_write_investment_summary,
    create_write_remaining_sections,
)
from tradingagents.equity_research.agents.workflow_agents import create_plan_tables_and_charts
from tradingagents.equity_research.agents.forecast_agents import create_chart_generation
from tradingagents.equity_research.graph.routers import (
    final_qa_router,
    ic_router,
    modeling_router,
    research_loop_router,
    valuation_router,
)
from tradingagents.equity_research.state.equity_research_state import EquityResearchState


class EquityGraphSetup:
    def __init__(self, deps: EquityResearchDeps):
        self.deps = deps

    def setup_graph(self):
        g = StateGraph(EquityResearchState)

        g.add_node("initialize_state", create_initialize_state(self.deps))
        g.add_node("analyze_research_task", create_analyze_research_task(self.deps))
        g.add_node("dynamic_planning", create_dynamic_planning(self.deps))
        g.add_node("research_loop", create_research_loop(self.deps))
        g.add_node("modeling_workflow", create_modeling_workflow(self.deps))
        g.add_node("valuation_workflow", create_valuation_workflow(self.deps))
        g.add_node("branch_merge", create_branch_merge(self.deps))
        g.add_node("risk_mapping", create_risk_mapping(self.deps))
        g.add_node("investment_committee_review", create_investment_committee_review(self.deps))
        g.add_node("write_investment_focus", create_write_investment_summary(self.deps))
        g.add_node("write_remaining_sections", create_write_remaining_sections(self.deps))
        g.add_node("plan_tables_and_charts", create_plan_tables_and_charts(self.deps))
        g.add_node("chart_generation", create_chart_generation(self.deps))
        g.add_node("assemble_report", create_assemble_report(self.deps))
        g.add_node("final_qa", create_final_qa(self.deps))
        g.add_node("export_report", create_markdown_memory_export(self.deps))

        g.set_entry_point("initialize_state")
        g.add_edge("initialize_state", "analyze_research_task")
        g.add_edge("analyze_research_task", "dynamic_planning")
        g.add_edge("dynamic_planning", "research_loop")

        g.add_conditional_edges(
            "research_loop",
            research_loop_router,
            {
                "continue_research": "dynamic_planning",
                "ready_for_modeling": "modeling_workflow",
                "need_human_review": "investment_committee_review",
            },
        )

        g.add_conditional_edges(
            "modeling_workflow",
            modeling_router,
            {
                "pass": "valuation_workflow",
                "revise_assumptions": "modeling_workflow",
                "more_research": "dynamic_planning",
            },
        )

        g.add_conditional_edges(
            "valuation_workflow",
            valuation_router,
            {
                "pass": "branch_merge",
                "revise_valuation": "valuation_workflow",
                "revise_forecast": "modeling_workflow",
                "more_research": "dynamic_planning",
            },
        )

        g.add_edge("branch_merge", "risk_mapping")
        g.add_edge("risk_mapping", "investment_committee_review")

        g.add_conditional_edges(
            "investment_committee_review",
            ic_router,
            {
                "approve": "write_investment_focus",
                "revise_research": "dynamic_planning",
                "revise_model": "modeling_workflow",
                "revise_valuation": "valuation_workflow",
            },
        )

        g.add_edge("write_investment_focus", "write_remaining_sections")
        g.add_edge("write_remaining_sections", "plan_tables_and_charts")
        g.add_edge("plan_tables_and_charts", "chart_generation")
        g.add_edge("chart_generation", "assemble_report")
        g.add_edge("assemble_report", "final_qa")

        g.add_conditional_edges(
            "final_qa",
            final_qa_router,
            {
                "pass": "export_report",
                "revise_report": "assemble_report",
                "revise_research": "dynamic_planning",
                "revise_model": "modeling_workflow",
            },
        )

        g.add_edge("export_report", END)
        return g
