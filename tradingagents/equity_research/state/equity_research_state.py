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
        "mandate": {},
        "report_template": [],
        "active_section_id": None,
        "section_coverage": {},
        "completed_sections": [],
        "source_index": [],
        "broker_views": [],
        "consensus_view": {},
        "consensus_report": "",
        "consensus_coverage_report": {},
        "consensus_assumptions": {},
        "consensus_iterations": 0,
        "max_consensus_iterations": 5,
        "consensus_evidence_buffer": [],
        "consensus_search_memory": [],
        "assumption_view": {},
        "assumption_map": [],
        "assumption_report": "",
        "assumption_coverage_report": {},
        "assumption_search_memory": [],
        "assumption_evidence_buffer": [],
        "research_suggestions": [],
        "research_directions": [],
        "max_assumption_iterations": 3,
        "expectation_gaps": [],
        "research_plan": {},
        "section_plans": {},
        "planner_exploration_graph": {"nodes": {}, "branch_roots": {}},
        "active_objective": "",
        "completed_objectives": [],
        "research_gaps": [],
        "research_status": "pending",
        "research_iterations": 0,
        "max_research_iterations": 5,
        "thesis_ledger": [],
        "evidence_ledger": [],
        "claim_ledger": [],
        "assumption_ledger": [],
        "consensus_ledger": [],
        "broker_view_ledger": [],
        "forecast_ledger": [],
        "valuation_ledger": [],
        "issue_ledger": [],
        "research_graph": {"nodes": {}, "edges": [], "best_node_id": None, "branches": {}},
        "research_strategy": {},
        "task_analysis": {},
        "subgraph_outputs": {},
        "metric_store": {},
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
        "historical_financials": {},
        "operating_kpis": {},
        "forecast_model": None,
        "model_assumptions": [],
        "valuation_method": None,
        "valuation_model": None,
        "scenario_analysis": {},
        "target_price": None,
        "rating": None,
        "dividend_yield_pct": 0.0,
        "sensitivity_results": [],
        "risk_map": [],
        "catalyst_calendar": [],
        "claims": [],
        "section_drafts": {},
        "final_report": None,
        "cross_branch_discoveries": [],
        "research_traces": [],
        "review_findings": [],
        "data_quality_flags": [],
        "compliance_flags": [],
        "warnings": [],
        "errors": [],
        "chart_placeholders": [],
        "ic_review": None,
        "started_at": now,
        "last_updated": now,
        "tokens_consumed": 0,
        "api_calls": 0,
        "skill_catalog": [],
        "loaded_skills": [],
        "next_route": "",
        "_route": "",
        "_hypothesis_route": "",
    }


class EquityResearchState(TypedDict, total=False):
    ticker: str
    report_id: str
    company_name: str
    trade_date: str
    sector: str
    industry: str
    report_type: str
    time_horizon: str
    current_price: float
    currency: str
    instrument_context: str
    mandate: dict
    report_template: list[dict]
    active_section_id: str | None
    section_coverage: dict[str, dict]
    completed_sections: list[str]
    source_index: list[dict]
    broker_views: list[dict]
    consensus_view: dict
    consensus_report: str
    consensus_coverage_report: dict
    consensus_assumptions: dict
    consensus_iterations: int
    max_consensus_iterations: int
    consensus_evidence_buffer: list[dict]
    consensus_search_memory: list[dict]
    assumption_view: dict
    assumption_map: list[dict]
    assumption_report: str
    assumption_coverage_report: dict
    assumption_search_memory: list[dict]
    assumption_evidence_buffer: list[dict]
    research_suggestions: list[dict]
    research_directions: list[str]
    max_assumption_iterations: int
    expectation_gaps: list[dict]
    research_plan: dict
    section_plans: dict[str, dict]
    planner_exploration_graph: dict
    active_objective: str
    completed_objectives: list[str]
    research_gaps: list[dict]
    research_status: str
    research_iterations: int
    max_research_iterations: int
    thesis_ledger: list[dict]
    evidence_ledger: list[dict]
    claim_ledger: list[dict]
    assumption_ledger: list[dict]
    consensus_ledger: list[dict]
    broker_view_ledger: list[dict]
    forecast_ledger: list[dict]
    valuation_ledger: list[dict]
    issue_ledger: list[dict]
    research_graph: dict
    research_strategy: dict
    task_analysis: dict
    subgraph_outputs: dict[str, dict[str, Any]]
    metric_store: dict
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
    historical_financials: dict
    operating_kpis: dict
    forecast_model: dict | None
    model_assumptions: list[dict]
    valuation_method: str | None
    valuation_model: dict | None
    scenario_analysis: dict
    target_price: float | None
    rating: str | None
    dividend_yield_pct: float
    sensitivity_results: list[dict]
    risk_map: list[dict]
    catalyst_calendar: list[dict]
    claims: list[dict]
    section_drafts: dict[str, dict]
    final_report: str | None
    cross_branch_discoveries: list[dict]
    research_traces: list[dict]
    review_findings: list[dict]
    data_quality_flags: list[dict]
    compliance_flags: list[dict]
    warnings: list[str]
    errors: list[str]
    chart_placeholders: list[dict]
    ic_review: dict | None
    started_at: str
    last_updated: str
    tokens_consumed: int
    api_calls: int
    skill_catalog: list[dict]
    loaded_skills: list[str]
    next_route: str
    _route: str
    _hypothesis_route: str
