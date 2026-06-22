"""Pydantic models for equity research claims, hypotheses, and section drafts."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from tradingagents.agents.schemas import PortfolioRating


class ClaimType(str, Enum):
    DESCRIPTIVE = "descriptive_claim"
    INDUSTRY = "industry_claim"
    COMPETITIVE = "competitive_claim"
    DRIVER = "driver_claim"
    FORECAST = "forecast_claim"
    VALUATION = "valuation_claim"
    RISK = "risk_claim"
    RECOMMENDATION = "recommendation_claim"


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    VERIFIED = "verified"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    NEEDS_MORE_RESEARCH = "needs_more_research"


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IN_RESEARCH = "in_research"
    VERIFIED = "verified"
    REJECTED = "rejected"
    NEEDS_MORE_RESEARCH = "needs_more_research"


class HypothesisScores(BaseModel):
    materiality: float = 0.0
    variant_perception: float = 0.0
    model_linkage: float = 0.0
    verifiability: float = 0.0
    evidence_availability: float = 0.0
    novelty: float = 0.0
    research_cost: float = 0.0
    priority: float = 0.0


class HypothesisNode(BaseModel):
    hypothesis_id: str
    parent_id: str | None = None
    children_ids: list[str] = Field(default_factory=list)
    ticker: str
    section_targets: list[str] = Field(default_factory=list)
    statement: str
    consensus_view: str = ""
    variant_view: str = ""
    key_value_drivers: list[str] = Field(default_factory=list)
    required_evidence: list[str] = Field(default_factory=list)
    required_computation: list[str] = Field(default_factory=list)
    valuation_link: str = ""
    status: HypothesisStatus = HypothesisStatus.PROPOSED
    scores: HypothesisScores = Field(default_factory=HypothesisScores)
    evidence_strength: float = 0.0
    contradiction_risk: float = 0.0
    research_iterations: int = 0
    max_iterations: int = 3
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    computation_results: dict[str, Any] | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class Claim(BaseModel):
    claim_id: str
    hypothesis_id: str
    section_id: str
    claim_type: ClaimType
    text: str
    status: ClaimStatus = ClaimStatus.PROPOSED
    confidence: float = 0.0
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    supporting_computation_ids: list[str] = Field(default_factory=list)
    supporting_fact_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    is_core_thesis: bool = False
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class SectionDraft(BaseModel):
    section_id: str
    title: str
    body_markdown: str
    claim_ids: list[str] = Field(default_factory=list)
    completed_outputs: list[str] = Field(default_factory=list)
    review_passed: bool = False
    review_feedback: str = ""


class ConsensusView(BaseModel):
    summary: str
    analyst_consensus: str = ""
    implied_growth: str = ""
    price_implied_expectations: str = ""
    source_doc_ids: list[str] = Field(default_factory=list)


class ExpectationGap(BaseModel):
    gap_id: str
    description: str
    alpha_source: str
    materiality: float = 0.0
    verifiability: float = 0.0
    related_metrics: list[str] = Field(default_factory=list)


class ResearchBudget(BaseModel):
    max_search_queries: int = 5
    max_extraction_docs: int = 8
    max_hypothesis_iterations: int = 3
    max_llm_tokens: int = 200_000
    remaining_search_queries: int = 5
    remaining_extraction_docs: int = 8


class ValuationMockResult(BaseModel):
    method: str = "pe_ev_multiples_mock"
    current_price: float
    target_price: float
    upside_pct: float
    rating: PortfolioRating
    peer_median_pe: float | None = None
    implied_pe: float | None = None
    notes: str = "MVP1 mock valuation — not a DCF model."
    is_mock: bool = True


class ChartPlaceholder(BaseModel):
    chart_id: str
    title: str
    time_range: str
    x_axis: str
    y_axis: str
    data_source: str
    processing_method: str
    file_path: str | None = None


class InvestmentCommitteeReview(BaseModel):
    passed: bool
    score: float
    blocking_issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rating: PortfolioRating | None = None
    target_price: float | None = None


def claim_to_dict(claim: Claim) -> dict[str, Any]:
    data = claim.model_dump()
    data["claim_type"] = claim.claim_type.value
    data["status"] = claim.status.value
    return data


def hypothesis_to_dict(node: HypothesisNode) -> dict[str, Any]:
    data = node.model_dump()
    data["status"] = node.status.value
    return data
