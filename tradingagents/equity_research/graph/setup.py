"""LangGraph setup for Deep Equity Research."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from tradingagents.equity_research.agents.consensus_agents import (
    create_discover_consensus,
    create_find_expectation_gaps,
)
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.evidence_agents import (
    create_evaluate_stop_condition,
    create_extract_facts,
    create_retrieve_evidence,
    create_verify_claims,
)
from tradingagents.equity_research.agents.final_agents import (
    create_assemble_report,
    create_investment_committee_review,
    create_markdown_memory_export,
)
from tradingagents.equity_research.agents.forecast_agents import (
    create_business_driver_decomp,
    create_chart_generation,
    create_financial_forecast,
    create_valuation_mock,
)
from tradingagents.equity_research.agents.hypothesis_agents import (
    create_allocate_budget,
    create_generate_hypotheses,
    create_virtual_evaluate,
)
from tradingagents.equity_research.agents.init_agents import (
    create_initialize_state,
    create_load_report_template,
)
from tradingagents.equity_research.agents.writing_agents import (
    create_review_section,
    create_write_investment_focus,
    create_write_section,
)
from tradingagents.equity_research.graph.routers import (
    hypothesis_loop_router,
    section_loop_router,
    set_active_section,
)
from tradingagents.equity_research.state.equity_research_state import EquityResearchState


class EquityGraphSetup:
    def __init__(self, deps: EquityResearchDeps):
        self.deps = deps

    def setup_graph(self):
        g = StateGraph(EquityResearchState)

        g.add_node("initialize_state", create_initialize_state(self.deps))
        g.add_node("load_report_template", create_load_report_template(self.deps))
        g.add_node("discover_consensus", create_discover_consensus(self.deps))
        g.add_node("find_expectation_gaps", create_find_expectation_gaps(self.deps))
        g.add_node("section_entry", self._section_entry)
        g.add_node("generate_hypotheses", create_generate_hypotheses(self.deps))
        g.add_node("virtual_evaluate", create_virtual_evaluate(self.deps))
        g.add_node("allocate_budget", create_allocate_budget(self.deps))
        g.add_node("retrieve_evidence", create_retrieve_evidence(self.deps))
        g.add_node("extract_facts", create_extract_facts(self.deps))
        g.add_node("verify_claims", create_verify_claims(self.deps))
        g.add_node("evaluate_stop_condition", create_evaluate_stop_condition(self.deps))
        g.add_node("write_section", create_write_section(self.deps))
        g.add_node("write_investment_focus", create_write_investment_focus(self.deps))
        g.add_node("review_section", create_review_section(self.deps))
        g.add_node("business_driver_decomp", create_business_driver_decomp(self.deps))
        g.add_node("financial_forecast", create_financial_forecast(self.deps))
        g.add_node("valuation_mock", create_valuation_mock(self.deps))
        g.add_node("investment_committee_review", create_investment_committee_review(self.deps))
        g.add_node("assemble_report", create_assemble_report(self.deps))
        g.add_node("chart_generation", create_chart_generation(self.deps))
        g.add_node("markdown_memory_export", create_markdown_memory_export(self.deps))

        g.set_entry_point("initialize_state")
        g.add_edge("initialize_state", "load_report_template")
        g.add_edge("load_report_template", "discover_consensus")
        g.add_edge("discover_consensus", "find_expectation_gaps")
        g.add_edge("find_expectation_gaps", "section_entry")

        g.add_conditional_edges(
            "section_entry",
            section_loop_router,
            {
                "generate_hypotheses": "generate_hypotheses",
                "business_driver_decomp": "business_driver_decomp",
                "valuation_mock": "valuation_mock",
                "write_investment_focus": "write_investment_focus",
                "investment_committee_review": "investment_committee_review",
            },
        )

        g.add_edge("generate_hypotheses", "virtual_evaluate")
        g.add_edge("virtual_evaluate", "allocate_budget")
        g.add_edge("allocate_budget", "retrieve_evidence")
        g.add_edge("retrieve_evidence", "extract_facts")
        g.add_edge("extract_facts", "verify_claims")
        g.add_edge("verify_claims", "evaluate_stop_condition")

        g.add_conditional_edges(
            "evaluate_stop_condition",
            hypothesis_loop_router,
            {
                "retrieve_evidence": "retrieve_evidence",
                "write_section": "write_section",
            },
        )

        g.add_edge("write_section", "review_section")
        g.add_edge("business_driver_decomp", "financial_forecast")
        g.add_edge("financial_forecast", "write_section")
        g.add_edge("valuation_mock", "write_section")
        g.add_edge("write_investment_focus", "review_section")
        g.add_edge("review_section", "section_entry")

        g.add_edge("investment_committee_review", "assemble_report")
        g.add_edge("assemble_report", "chart_generation")
        g.add_edge("chart_generation", "markdown_memory_export")
        g.add_edge("markdown_memory_export", END)

        return g

    def _section_entry(self, state: dict):
        route = section_loop_router(state)
        updates = set_active_section(state, route)
        return updates
