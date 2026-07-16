"""Score merge helpers."""

from __future__ import annotations

from evaluation.section_research.judge.rubric import weighted_judge_overall
from evaluation.section_research.types import (
    EvalBundle,
    JudgeBreakdown,
    RubricBreakdown,
    ScoreReport,
)


def merge_scores(
    bundle: EvalBundle,
    *,
    completion_score: float,
    schema_score: float,
    trajectory_score: float,
    judge: JudgeBreakdown | None,
    rubric: RubricBreakdown,
    details: dict | None = None,
) -> ScoreReport:
    det = (completion_score + schema_score + trajectory_score) / 3.0
    judge_overall = None
    faithfulness = None
    if judge is not None:
        faithfulness = judge.faithfulness
        judge_overall = judge.overall
        if judge_overall <= 0:
            judge_overall = weighted_judge_overall(judge.model_dump(), rubric)
            judge.overall = judge_overall

    if judge is not None and judge_overall is not None:
        overall = rubric.det_weight * det + rubric.judge_weight * judge_overall
    else:
        overall = det

    expected = bundle.fixture_meta.expected_scores or {}
    deltas: dict[str, float] = {}
    for key, exp in expected.items():
        actual_map = {
            "completion_score": completion_score,
            "schema_score": schema_score,
            "trajectory_score": trajectory_score,
            "faithfulness_score": faithfulness if faithfulness is not None else 0.0,
            "judge_overall": judge_overall if judge_overall is not None else 0.0,
            "overall_score": overall,
            "content_quality": judge.content_quality if judge else 0.0,
            "coverage_vs_plan": judge.coverage_vs_plan if judge else 0.0,
            "faithfulness": faithfulness if faithfulness is not None else 0.0,
            "gaps_honesty": judge.gaps_honesty if judge else 0.0,
            "overall": judge_overall if judge_overall is not None else overall,
        }
        if key in actual_map:
            deltas[key] = round(float(actual_map[key]) - float(exp), 4)

    return ScoreReport(
        ticker=bundle.ticker,
        section_id=bundle.section_id,
        case_id=bundle.fixture_meta.case_id,
        source=bundle.source,
        run_id=bundle.run_id,
        completion_score=completion_score,
        schema_score=schema_score,
        trajectory_score=trajectory_score,
        judge=judge,
        faithfulness_score=faithfulness,
        judge_overall=judge_overall,
        overall_score=round(overall, 4),
        deltas=deltas,
        details=details or {},
    )


def deltas_exceed_threshold(report: ScoreReport, rubric: RubricBreakdown) -> list[str]:
    failed: list[str] = []
    for key, delta in report.deltas.items():
        if abs(delta) > rubric.max_delta_fail:
            failed.append(key)
    return failed
