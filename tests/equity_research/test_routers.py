"""Unit tests for section and hypothesis routers."""

from tradingagents.equity_research.graph.routers import hypothesis_loop_router, section_loop_router
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


def test_section_loop_router_priority():
    state = empty_equity_research_state()
    assert section_loop_router(state) == "generate_hypotheses"

    state["completed_sections"] = [
        "2_company_overview",
        "3_industry_and_competition",
    ]
    assert section_loop_router(state) == "business_driver_decomp"

    state["completed_sections"].extend(["5_earnings_forecast", "6_valuation", "7_risks"])
    assert section_loop_router(state) == "write_investment_focus"

    state["completed_sections"].append("1_investment_focus")
    assert section_loop_router(state) == "investment_committee_review"


def test_hypothesis_loop_router_uses_route_flag():
    state = empty_equity_research_state()
    state["_hypothesis_route"] = "retrieve_evidence"
    assert hypothesis_loop_router(state) == "retrieve_evidence"
    state["_hypothesis_route"] = "write_section"
    assert hypothesis_loop_router(state) == "write_section"
