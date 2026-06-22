"""Conditional routing for section and hypothesis loops."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.templates.report_template import MVP1_SECTION_ORDER

SPECIAL_SECTION_HANDLERS = {
    "5_earnings_forecast": "business_driver_decomp",
    "6_valuation": "valuation_mock",
    "1_investment_focus": "write_investment_focus",
}

HYPOTHESIS_SECTIONS = {"2_company_overview", "3_industry_and_competition", "7_risks"}


def section_loop_router(state: dict[str, Any]) -> str:
    completed = set(state.get("completed_sections", []))
    for section_id in MVP1_SECTION_ORDER:
        if section_id not in completed:
            if section_id in SPECIAL_SECTION_HANDLERS:
                return SPECIAL_SECTION_HANDLERS[section_id]
            if section_id in HYPOTHESIS_SECTIONS:
                return "generate_hypotheses"
    return "investment_committee_review"


def set_active_section(state: dict[str, Any], route: str) -> dict[str, Any]:
    """Map route target back to active_section_id for downstream agents."""
    reverse = {v: k for k, v in SPECIAL_SECTION_HANDLERS.items()}
    reverse["generate_hypotheses"] = _next_hypothesis_section(state)
    section_id = reverse.get(route)
    if section_id:
        return {"active_section_id": section_id}
    return {}


def _next_hypothesis_section(state: dict[str, Any]) -> str:
    completed = set(state.get("completed_sections", []))
    for section_id in MVP1_SECTION_ORDER:
        if section_id in HYPOTHESIS_SECTIONS and section_id not in completed:
            return section_id
    return "2_company_overview"


def hypothesis_loop_router(state: dict[str, Any]) -> str:
    return state.get("_hypothesis_route", "write_section")


def route_after_section_entry(state: dict[str, Any]) -> str:
    """Used when entering section loop — pick first node."""
    route = section_loop_router(state)
    updates = set_active_section(state, route)
    state.update(updates)
    return route
