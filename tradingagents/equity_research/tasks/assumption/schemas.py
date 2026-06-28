"""Schemas for assumption research task."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from tradingagents.equity_research.state.consensus_schemas import (
    ConsensusAssumptions,
    CoverageStatus,
)

ASSUMPTION_DIMENSIONS: tuple[str, ...] = (
    "business_model",
    "market_sentiment",
    "key_metrics",
    "valuation",
    "earnings_focus",
    "expectation_changes",
    "benchmark_expectations",
    "model_drivers",
    "debates",
    "stress_test",
    "next_data",
)


class ResearchSuggestion(BaseModel):
    direction: str = ""
    rationale: str = ""
    priority: int = 3
    related_assumption: str = ""


class AssumptionView(BaseModel):
    ticker: str = ""
    as_of: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    coverage_score: float = 0.0
    current_assumptions: ConsensusAssumptions = Field(default_factory=ConsensusAssumptions)
    research_suggestions: list[ResearchSuggestion] = Field(default_factory=list)
    research_directions: list[str] = Field(default_factory=list)
    dimension_coverage: dict[str, CoverageStatus] = Field(default_factory=dict)
    source_doc_ids: list[str] = Field(default_factory=list)


class AssumptionViewUpdate(BaseModel):
    current_assumptions: ConsensusAssumptions | None = None
    research_suggestions: list[ResearchSuggestion] | None = None
    research_directions: list[str] | None = None
    dimension_coverage: dict[str, CoverageStatus] | None = None
    coverage_score: float | None = None
    source_doc_ids: list[str] | None = None


class AssumptionCoverageEvaluation(BaseModel):
    dimension_scores: dict[str, CoverageStatus] = Field(default_factory=dict)
    overall_score: float = 0.0
    critical_gaps: list[str] = Field(default_factory=list)
    suggested_focus: list[str] = Field(default_factory=list)


def empty_assumption_view(ticker: str) -> AssumptionView:
    return AssumptionView(ticker=ticker)
