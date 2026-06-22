"""Unit tests for Equity R&D-Agent workflow routers."""

from tradingagents.equity_research.graph.routers import (
    final_qa_router,
    ic_router,
    modeling_router,
    research_loop_router,
    valuation_router,
)
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


def test_research_loop_router_ready_for_modeling():
    state = empty_equity_research_state()
    state["research_status"] = "sufficient"
    assert research_loop_router(state) == "ready_for_modeling"


def test_research_loop_router_continues():
    state = empty_equity_research_state()
    state["research_status"] = "continue"
    state["research_iterations"] = 1
    assert research_loop_router(state) == "continue_research"


def test_modeling_router_pass():
    state = empty_equity_research_state()
    state["next_route"] = "pass"
    assert modeling_router(state) == "pass"


def test_valuation_router_revise():
    state = empty_equity_research_state()
    state["next_route"] = "revise_valuation"
    assert valuation_router(state) == "revise_valuation"


def test_ic_router_approve():
    state = empty_equity_research_state()
    state["ic_review"] = {"passed": True, "blocking_issues": []}
    assert ic_router(state) == "approve"


def test_ic_router_revise_research():
    state = empty_equity_research_state()
    state["ic_review"] = {"passed": False, "blocking_issues": ["no_variant_view"]}
    assert ic_router(state) == "revise_research"


def test_final_qa_router_pass():
    state = empty_equity_research_state()
    state["next_route"] = "pass"
    assert final_qa_router(state) == "pass"
