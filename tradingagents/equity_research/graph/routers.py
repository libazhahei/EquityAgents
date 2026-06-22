"""Conditional routing for Equity R&D-Agent workflow."""

from __future__ import annotations

from typing import Any


def research_loop_router(state: dict[str, Any]) -> str:
    status = state.get("research_status", "continue")
    iterations = int(state.get("research_iterations", 0))
    max_iterations = int(state.get("max_research_iterations", 5))
    if status == "sufficient" or iterations >= max_iterations:
        return "ready_for_modeling"
    if status == "needs_human":
        return "need_human_review"
    return "continue_research"


def modeling_router(state: dict[str, Any]) -> str:
    route = state.get("next_route", "pass")
    if route == "more_research":
        return "more_research"
    if route == "revise_assumptions":
        return "revise_assumptions"
    return "pass"


def valuation_router(state: dict[str, Any]) -> str:
    route = state.get("next_route", "pass")
    if route == "revise_forecast":
        return "revise_forecast"
    if route == "revise_valuation":
        return "revise_valuation"
    if route == "more_research":
        return "more_research"
    return "pass"


def ic_router(state: dict[str, Any]) -> str:
    ic = state.get("ic_review") or {}
    if ic.get("passed"):
        return "approve"
    blocking = ic.get("blocking_issues", [])
    if any("forecast" in b for b in blocking):
        return "revise_model"
    if any("valuation" in b or "rating" in b or "target_price" in b for b in blocking):
        return "revise_valuation"
    if any("research" in b or "variant" in b or "evidence" in b for b in blocking):
        return "revise_research"
    return "revise_research"


def final_qa_router(state: dict[str, Any]) -> str:
    route = state.get("next_route", "pass")
    if route == "fail":
        return "revise_report"
    findings = state.get("review_findings", [])
    if any("forecast" in str(f) for f in findings):
        return "revise_model"
    if any("research" in str(f) for f in findings):
        return "revise_research"
    return "pass"


# Legacy aliases for backward compatibility in tests
research_completion_router = research_loop_router
forecast_router = modeling_router
ic_review_router = ic_router


def human_review_router(state: dict[str, Any]) -> str:
    return state.get("next_route", "ready_for_modeling")
