"""LangGraph state for Deep Equity Research workflow."""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict


def empty_equity_research_state() -> dict[str, Any]:
    """Return a fresh state dict with all required keys defaulted."""
    now = datetime.utcnow().isoformat()
    return {
        "ticker": "",
        "report_id": "",
        "company_name": "",
        "sector": "",
        "industry": "",
        "report_type": "initiation",
        "time_horizon": "12m",
        "current_price": 0.0,
        "currency": "USD",
        "instrument_context": "",
        "report_template": [],
        "active_section_id": None,
        "section_coverage": {},
        "completed_sections": [],
        "consensus_view": [],
        "expectation_gaps": [],
        "hypothesis_nodes": {},
        "active_hypothesis_ids": [],
        "pruned_hypothesis_ids": [],
        "verified_hypothesis_ids": [],
        "research_phase": "early",
        "research_budget": {},
        "documents": [],
        "evidence_fragments": [],
        "contradiction_fragments": [],
        "structured_facts": [],
        "fact_conflicts": [],
        "business_drivers": [],
        "forecast_model": None,
        "model_assumptions": [],
        "valuation_method": None,
        "valuation_model": None,
        "target_price": None,
        "rating": None,
        "sensitivity_results": [],
        "claims": [],
        "section_drafts": {},
        "final_report": None,
        "cross_branch_discoveries": [],
        "research_traces": [],
        "warnings": [],
        "errors": [],
        "chart_placeholders": [],
        "ic_review": None,
        "started_at": now,
        "last_updated": now,
        "tokens_consumed": 0,
        "api_calls": 0,
        "_route": "",
        "_hypothesis_route": "",
    }


class EquityResearchState(TypedDict, total=False):
    ticker: str
    report_id: str
    company_name: str
    sector: str
    industry: str
    report_type: str
    time_horizon: str
    current_price: float
    currency: str
    instrument_context: str
    report_template: list[dict]
    active_section_id: str | None
    section_coverage: dict[str, dict]
    completed_sections: list[str]
    consensus_view: list[dict]
    expectation_gaps: list[dict]
    hypothesis_nodes: dict[str, dict]
    active_hypothesis_ids: list[str]
    pruned_hypothesis_ids: list[str]
    verified_hypothesis_ids: list[str]
    research_phase: str
    research_budget: dict
    documents: list[dict]
    evidence_fragments: list[dict]
    contradiction_fragments: list[dict]
    structured_facts: list[dict]
    fact_conflicts: list[dict]
    business_drivers: list[dict]
    forecast_model: dict | None
    model_assumptions: list[dict]
    valuation_method: str | None
    valuation_model: dict | None
    target_price: float | None
    rating: str | None
    sensitivity_results: list[dict]
    claims: list[dict]
    section_drafts: dict[str, dict]
    final_report: str | None
    cross_branch_discoveries: list[dict]
    research_traces: list[dict]
    warnings: list[str]
    errors: list[str]
    chart_placeholders: list[dict]
    ic_review: dict | None
    started_at: str
    last_updated: str
    tokens_consumed: int
    api_calls: int
    _route: str
    _hypothesis_route: str
