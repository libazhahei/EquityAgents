"""Structured consensus view schemas for the consensus subgraph."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


CONSENSUS_DIMENSIONS = (
    "quantitative_estimates",
    "kpi_focus",
    "pricing_assumptions",
    "narrative_framework",
    "recent_delta",
)


class CoverageStatus(str, Enum):
    EMPTY = "empty"
    PARTIAL = "partial"
    SUFFICIENT = "sufficient"
    STRONG = "strong"


class SearchMode(str, Enum):
    EXPLORATORY = "exploratory"
    TARGETED = "targeted"
    CONTRADICTION = "contradiction"


class YearEstimate(BaseModel):
    low: str = ""
    median: str = ""
    high: str = ""
    currency: str = "USD"
    period: str = ""
    period_end: str = ""
    estimate_type: str = ""
    basis: str = ""
    as_of: str = ""
    source_quality: str = ""


class SourceCitation(BaseModel):
    url: str = ""
    source_type: str = ""
    reliability: str = ""
    used_for: str = ""


class ConflictRecord(BaseModel):
    claim_a: str = ""
    claim_b: str = ""
    interpretation: str = ""
    resolution_status: str = "unresolved"
    next_check: str = ""


class EstimateRange(BaseModel):
    year_1: YearEstimate = Field(default_factory=YearEstimate)
    year_2: YearEstimate = Field(default_factory=YearEstimate)
    year_3: YearEstimate = Field(default_factory=YearEstimate)


class KPIItem(BaseModel):
    name: str = ""
    expected_level: str = ""
    importance: str = ""
    rationale: str = ""


class DeltaItem(BaseModel):
    metric: str = ""
    actual: str = ""
    expected: str = ""
    delta: str = ""


class PeerItem(BaseModel):
    ticker: str = ""
    metric: str = ""
    value: str = ""
    comparison: str = ""


class QuantitativeEstimates(BaseModel):
    revenue_estimates: EstimateRange = Field(default_factory=EstimateRange)
    earnings_estimates: EstimateRange = Field(default_factory=EstimateRange)
    fcf_estimates: EstimateRange = Field(default_factory=EstimateRange)
    analyst_count: int = 0
    sources: list[str] = Field(default_factory=list)

    @field_validator("sources", mode="before")
    @classmethod
    def normalize_sources(cls, value: Any) -> list[str]:
        if not value:
            return []
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                out.append(str(item.get("url", "")))
            elif hasattr(item, "url"):
                out.append(str(item.url))
        return [u for u in out if u]


class KPIFocus(BaseModel):
    primary_kpis: list[KPIItem] = Field(default_factory=list)
    recent_actuals_vs_expected: list[DeltaItem] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class PricingAssumptions(BaseModel):
    implied_growth_rate: str = ""
    current_multiples: dict[str, str] = Field(default_factory=dict)
    peer_comparison: list[PeerItem] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class NarrativeFramework(BaseModel):
    bull_case: str = ""
    bear_case: str = ""
    key_debates: list[str] = Field(default_factory=list)
    growth_drivers: list[str] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class RecentDelta(BaseModel):
    estimate_revisions: str = ""
    guidance_change: str = ""
    sentiment_shift: str = ""
    sources: list[str] = Field(default_factory=list)


class QueryItem(BaseModel):
    query: str
    target_dimension: str
    mode: SearchMode = SearchMode.EXPLORATORY
    priority: int = 1


class EvidenceItem(BaseModel):
    answer: str = ""
    citations: list[str] = Field(default_factory=list)
    target_dimension: str = ""
    query_used: str = ""
    retrieved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    doc_ids: list[str] = Field(default_factory=list)


class CoverageReport(BaseModel):
    dimension_scores: dict[str, CoverageStatus] = Field(default_factory=dict)
    overall_score: float = 0.0
    critical_gaps: list[str] = Field(default_factory=list)
    suggested_focus: list[str] = Field(default_factory=list)
    routing_decision: str = "continue"


class SkillSelectionResult(BaseModel):
    load_skills: list[str] = Field(default_factory=list)
    reason: str = ""

    @field_validator("load_skills")
    @classmethod
    def cap_skill_count(cls, value: list[str]) -> list[str]:
        return value[:2]


class QueryPlan(BaseModel):
    queries: list[QueryItem] = Field(default_factory=list)

    @field_validator("queries")
    @classmethod
    def cap_query_count(cls, value: list[QueryItem]) -> list[QueryItem]:
        return value[:5]


class ConsensusViewUpdate(BaseModel):
    """Partial consensus view update for incremental synthesis."""

    ticker: str = ""
    quantitative_estimates: QuantitativeEstimates | None = None
    kpi_focus: KPIFocus | None = None
    pricing_assumptions: PricingAssumptions | None = None
    narrative_framework: NarrativeFramework | None = None
    recent_delta: RecentDelta | None = None
    dimension_coverage: dict[str, CoverageStatus] | None = None
    conflicts: list[ConflictRecord] | None = None


class CoverageEvaluation(BaseModel):
    dimension_scores: dict[str, CoverageStatus] = Field(default_factory=dict)
    overall_score: float = 0.0
    critical_gaps: list[str] = Field(default_factory=list)
    suggested_focus: list[str] = Field(default_factory=list)


class ExpectationGapInput(BaseModel):
    description: str = ""
    alpha_source: str = ""
    materiality: float = 0.5
    verifiability: float = 0.5
    related_metrics: list[str] = Field(default_factory=list)
    source_dimension: str = ""
    consensus_assumption: str = ""
    variant_view: str = ""


class ExpectationGapBatch(BaseModel):
    gaps: list[ExpectationGapInput] = Field(default_factory=list)

    @field_validator("gaps")
    @classmethod
    def cap_gap_count(cls, value: list[ExpectationGapInput]) -> list[ExpectationGapInput]:
        return value[:4]


class ConsensusAssumptions(BaseModel):
    business_model: str = ""
    market_sentiment: str = ""
    key_metrics_watched: list[str] = Field(default_factory=list)
    valuation_rationale: str = ""
    earnings_focus: str = ""
    recent_expectation_changes: str = ""
    benchmark_expectations: str = ""
    sellside_model_drivers: list[str] = Field(default_factory=list)
    key_debates: list[str] = Field(default_factory=list)
    stress_test_candidates: list[str] = Field(default_factory=list)
    recommended_next_data: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class SearchRecord(BaseModel):
    record_id: str = ""
    iteration: int = 0
    query: str = ""
    target_dimension: str = ""
    mode: str = ""
    answer: str = ""
    answer_summary: str = ""
    citations: list[str] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)
    retrieved_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class StructuredConsensusView(BaseModel):
    ticker: str = ""
    as_of: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    coverage_score: float = 0.0
    quantitative_estimates: QuantitativeEstimates = Field(default_factory=QuantitativeEstimates)
    kpi_focus: KPIFocus = Field(default_factory=KPIFocus)
    pricing_assumptions: PricingAssumptions = Field(default_factory=PricingAssumptions)
    narrative_framework: NarrativeFramework = Field(default_factory=NarrativeFramework)
    recent_delta: RecentDelta = Field(default_factory=RecentDelta)
    dimension_coverage: dict[str, CoverageStatus] = Field(default_factory=dict)
    source_doc_ids: list[str] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)

    def to_legacy_summary(self, max_length: int = 4000) -> str:
        parts: list[str] = []
        qe = self.quantitative_estimates
        if qe.analyst_count or qe.sources:
            parts.append(
                f"Quantitative estimates (analysts: {qe.analyst_count}): "
                f"{json.dumps(qe.model_dump(), default=str)[:800]}"
            )
        kpi = self.kpi_focus
        if kpi.primary_kpis or kpi.sources:
            parts.append(f"KPI focus: {json.dumps(kpi.model_dump(), default=str)[:600]}")
        pa = self.pricing_assumptions
        if pa.implied_growth_rate or pa.sources:
            parts.append(
                f"Pricing assumptions (implied growth: {pa.implied_growth_rate}): "
                f"{json.dumps(pa.model_dump(), default=str)[:500]}"
            )
        nf = self.narrative_framework
        if nf.bull_case or nf.bear_case or nf.key_debates:
            parts.append(
                f"Narrative — Bull: {nf.bull_case[:300]}; Bear: {nf.bear_case[:300]}; "
                f"Debates: {', '.join(nf.key_debates[:5])}"
            )
        rd = self.recent_delta
        if rd.estimate_revisions or rd.guidance_change or rd.sentiment_shift:
            parts.append(
                f"Recent delta — Revisions: {rd.estimate_revisions[:200]}; "
                f"Guidance: {rd.guidance_change[:200]}; Sentiment: {rd.sentiment_shift[:200]}"
            )
        if not parts:
            return f"No structured consensus data for {self.ticker}."
        return "\n\n".join(parts)[:max_length]

    def to_ledger_entries(self) -> list[dict[str, Any]]:
        entries = []
        summary = self.to_legacy_summary()
        entries.append({
            "consensus_id": f"cons_{self.ticker}_overall",
            "metric": "overall",
            "summary": summary[:500],
            "value": summary[:500],
            "source": "consensus_subgraph",
        })
        for dim in CONSENSUS_DIMENSIONS:
            status = self.dimension_coverage.get(dim, CoverageStatus.EMPTY)
            if isinstance(status, CoverageStatus):
                status = status.value
            entries.append({
                "consensus_id": f"cons_{self.ticker}_{dim}",
                "metric": dim,
                "summary": status,
                "value": status,
                "source": "consensus_subgraph",
            })
        return entries


def empty_structured_consensus_view(ticker: str = "") -> StructuredConsensusView:
    return StructuredConsensusView(
        ticker=ticker,
        dimension_coverage={dim: CoverageStatus.EMPTY for dim in CONSENSUS_DIMENSIONS},
    )


def get_consensus_summary(state: dict[str, Any], max_length: int = 4000) -> str:
    view = state.get("consensus_view") or {}
    if isinstance(view, list):
        return (view[0] if view else {}).get("summary", "")
    if not view:
        return ""
    try:
        return StructuredConsensusView.model_validate(view).to_legacy_summary(max_length=max_length)
    except Exception:
        return str(view.get("summary", ""))[:max_length]


def get_consensus_view_for_prompt(state: dict[str, Any]) -> str:
    return get_consensus_summary(state, max_length=6000)
    # view = state.get("consensus_view") or {}
    # if isinstance(view, list):
    #     return json.dumps(view[:2], default=str)
    # if not view:
    #     return "{}"
    # try:
    #     validated = StructuredConsensusView.model_validate(view)
    #     return json.dumps(validated.model_dump(), default=str)[:6000]
    # except Exception:
    #     return json.dumps(view, default=str)[:6000]
