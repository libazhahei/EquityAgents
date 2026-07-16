"""Rubric loading and markdown breakdown table for the judge prompt."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.section_research.types import RubricBreakdown, RubricDimension

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_RUBRIC_PATH = _ROOT / "datasets" / "rubric_default.json"


def load_rubric(path: Path | None = None) -> RubricBreakdown:
    target = path or _DEFAULT_RUBRIC_PATH
    data = json.loads(target.read_text(encoding="utf-8"))
    return RubricBreakdown.model_validate(data)


def merge_rubric(
    default: RubricBreakdown,
    override: RubricBreakdown | None,
) -> RubricBreakdown:
    if override is None:
        return default
    dims = override.dimensions or default.dimensions
    return RubricBreakdown(
        dimensions=dims,
        max_delta_fail=override.max_delta_fail
        if override.max_delta_fail is not None
        else default.max_delta_fail,
        det_weight=override.det_weight if override.det_weight is not None else default.det_weight,
        judge_weight=override.judge_weight
        if override.judge_weight is not None
        else default.judge_weight,
    )


def rubric_markdown_table(rubric: RubricBreakdown) -> str:
    lines = [
        "| Dimension | Weight | Meaning (0–1) | Fail cues |",
        "|---|---:|---|---|",
    ]
    for dim in rubric.dimensions:
        lines.append(
            f"| {dim.name} | {dim.weight:.2f} | {dim.meaning} | {dim.fail_cues} |"
        )
    return "\n".join(lines)


def weighted_judge_overall(scores: dict[str, float], rubric: RubricBreakdown) -> float:
    if not rubric.dimensions:
        keys = ["content_quality", "coverage_vs_plan", "faithfulness", "gaps_honesty"]
        vals = [float(scores.get(k, 0.0)) for k in keys]
        return sum(vals) / len(vals) if vals else 0.0
    total_w = sum(d.weight for d in rubric.dimensions) or 1.0
    return sum(float(scores.get(d.name, 0.0)) * d.weight for d in rubric.dimensions) / total_w


DEFAULT_DIMENSIONS: list[RubricDimension] = load_rubric().dimensions
