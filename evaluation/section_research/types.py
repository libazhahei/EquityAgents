"""Shared types for section research evaluation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EvidencePack(BaseModel):
    tool_outputs: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ledger: list[dict[str, Any]] = Field(default_factory=list)
    pending_evidence: list[dict[str, Any]] = Field(default_factory=list)
    search_memory: list[dict[str, Any]] = Field(default_factory=list)


class RubricDimension(BaseModel):
    name: str
    weight: float = 0.0
    meaning: str = ""
    fail_cues: str = ""


class RubricBreakdown(BaseModel):
    dimensions: list[RubricDimension] = Field(default_factory=list)
    max_delta_fail: float = 0.15
    det_weight: float = 0.4
    judge_weight: float = 0.6


class FixtureMeta(BaseModel):
    case_id: str = ""
    ticker: str = ""
    section_id: str = "3_business_model"
    background_json: str | None = None
    planner_json: str | None = None
    rubric_breakdown: RubricBreakdown | None = None
    expected_scores: dict[str, float] = Field(default_factory=dict)
    reference_notes: str = ""
    max_iterations: int = 5
    mode: str = "wrapper"


class ChildRunSummary(BaseModel):
    name: str = ""
    run_type: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] | None = None
    error: str | None = None


class EvalBundle(BaseModel):
    ticker: str
    section_id: str
    final_state: dict[str, Any] = Field(default_factory=dict)
    child_runs: list[ChildRunSummary] = Field(default_factory=list)
    evidence: EvidencePack = Field(default_factory=EvidencePack)
    fixture_meta: FixtureMeta = Field(default_factory=FixtureMeta)
    source: str = "live"
    run_id: str | None = None


class JudgeBreakdown(BaseModel):
    content_quality: float = 0.0
    coverage_vs_plan: float = 0.0
    faithfulness: float = 0.0
    gaps_honesty: float = 0.0
    overall: float = 0.0
    rationale_by_dimension: dict[str, str] = Field(default_factory=dict)
    unsupported_claims: list[str] = Field(default_factory=list)


class ScoreReport(BaseModel):
    ticker: str = ""
    section_id: str = ""
    case_id: str = ""
    source: str = ""
    run_id: str | None = None

    completion_score: float = 0.0
    schema_score: float = 0.0
    trajectory_score: float = 0.0

    judge: JudgeBreakdown | None = None
    faithfulness_score: float | None = None
    judge_overall: float | None = None

    overall_score: float = 0.0
    deltas: dict[str, float] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)

    def metrics_dict(self) -> dict[str, float]:
        out: dict[str, float] = {
            "completion_score": self.completion_score,
            "schema_score": self.schema_score,
            "trajectory_score": self.trajectory_score,
            "overall_score": self.overall_score,
        }
        if self.faithfulness_score is not None:
            out["faithfulness_score"] = self.faithfulness_score
        if self.judge_overall is not None:
            out["judge_overall"] = self.judge_overall
        if self.judge is not None:
            out["content_quality"] = self.judge.content_quality
            out["coverage_vs_plan"] = self.judge.coverage_vs_plan
            out["gaps_honesty"] = self.judge.gaps_honesty
        for key, value in self.deltas.items():
            out[f"delta_{key}"] = value
        return out
