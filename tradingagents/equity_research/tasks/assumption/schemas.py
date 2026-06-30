"""Schemas for assumption research task."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from tradingagents.equity_research.state.consensus_schemas import ConflictRecord, CoverageStatus

ASSUMPTION_SEARCH_DIMENSIONS: tuple[str, ...] = (
    "demand_assumptions",
    "product_ramp_assumptions",
    "margin_assumptions",
    "competition_assumptions",
    "valuation_assumptions",
    "regulatory_assumptions",
    "estimate_revision_assumptions",
    "falsification_tests",
    "next_data_to_watch",
)

ASSUMPTION_QUALITY_DIMENSIONS: tuple[str, ...] = (
    "assumption_identification",
    "consensus_to_assumption_linkage",
    "model_driver_linkage",
    "evidence_balance",
    "falsifiability",
    "variant_view_detection",
    "research_actionability",
    "deduplication_quality",
    "source_quality",
)

# Backward-compatible alias
ASSUMPTION_DIMENSIONS = ASSUMPTION_SEARCH_DIMENSIONS


class AssumptionItem(BaseModel):
    id: str = ""
    statement: str = ""
    category: str = ""
    consensus_anchor: str = ""
    model_drivers: list[str] = Field(default_factory=list)
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    confidence: str = "medium"
    controversy_level: str = "medium"
    model_sensitivity: str = "medium"
    falsification_tests: list[str] = Field(default_factory=list)
    next_data_to_watch: list[str] = Field(default_factory=list)
    source_doc_ids: list[str] = Field(default_factory=list)


class ResearchSuggestion(BaseModel):
    direction: str = ""
    rationale: str = ""
    priority: int = 3
    related_assumption: str = ""
    related_assumptions: list[str] = Field(default_factory=list)
    next_checks: list[str] = Field(default_factory=list)


class AssumptionView(BaseModel):
    ticker: str = ""
    as_of: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    coverage_score: float = 0.0
    assumption_map: list[AssumptionItem] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    top_research_priorities: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    watchlist: list[str] = Field(default_factory=list)
    research_suggestions: list[ResearchSuggestion] = Field(default_factory=list)
    dimension_coverage: dict[str, CoverageStatus] = Field(default_factory=dict)
    source_doc_ids: list[str] = Field(default_factory=list)

    @property
    def research_directions(self) -> list[str]:
        return list(self.top_research_priorities)


class AssumptionViewUpdate(BaseModel):
    assumption_map: list[AssumptionItem] | None = None
    conflicts: list[ConflictRecord] | None = None
    top_research_priorities: list[str] | None = None
    open_questions: list[str] | None = None
    watchlist: list[str] | None = None
    research_suggestions: list[ResearchSuggestion] | None = None
    dimension_coverage: dict[str, CoverageStatus] | None = None
    coverage_score: float | None = None
    source_doc_ids: list[str] | None = None


class AssumptionCoverageEvaluation(BaseModel):
    dimension_scores: dict[str, CoverageStatus] = Field(default_factory=dict)
    overall_score: float = 0.0
    critical_gaps: list[str] = Field(default_factory=list)
    suggested_focus: list[str] = Field(default_factory=list)


def empty_assumption_view(ticker: str) -> AssumptionView:
    return AssumptionView(
        ticker=ticker,
        dimension_coverage={dim: CoverageStatus.EMPTY for dim in ASSUMPTION_QUALITY_DIMENSIONS},
    )


def assumption_map_to_legacy_shim(view: AssumptionView) -> dict:
    """Export compatibility dict for downstream consumers expecting consensus_assumptions."""
    items = {item.id or f"A{i+1}": item.statement for i, item in enumerate(view.assumption_map)}
    return {
        **items,
        "top_research_priorities": list(view.top_research_priorities),
        "assumption_count": len(view.assumption_map),
    }
