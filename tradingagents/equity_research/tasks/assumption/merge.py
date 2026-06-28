"""Merge utilities for assumption view updates."""

from __future__ import annotations

from tradingagents.equity_research.state.consensus_schemas import CoverageStatus
from tradingagents.equity_research.tasks.assumption.schemas import AssumptionView, AssumptionViewUpdate

_COVERAGE_ORDER = {
    CoverageStatus.EMPTY: 0,
    CoverageStatus.PARTIAL: 1,
    CoverageStatus.SUFFICIENT: 2,
    CoverageStatus.STRONG: 3,
}


def _merge_coverage(old: CoverageStatus | str | None, new: CoverageStatus | str | None) -> CoverageStatus:
    if isinstance(old, str):
        try:
            old = CoverageStatus(old)
        except ValueError:
            old = CoverageStatus.EMPTY
    if isinstance(new, str):
        try:
            new = CoverageStatus(new)
        except ValueError:
            new = CoverageStatus.EMPTY
    if old is None:
        return new or CoverageStatus.EMPTY
    if new is None:
        return old
    return new if _COVERAGE_ORDER.get(new, 0) > _COVERAGE_ORDER.get(old, 0) else old


def merge_assumption_view(view: AssumptionView, update: AssumptionViewUpdate) -> AssumptionView:
    data = view.model_dump()
    upd = update.model_dump(exclude_unset=True)

    if update.current_assumptions is not None:
        existing = view.current_assumptions.model_dump()
        for key, value in update.current_assumptions.model_dump(exclude_unset=True).items():
            if value is None:
                continue
            if isinstance(value, list) and isinstance(existing.get(key), list):
                existing[key] = list(dict.fromkeys([*(existing.get(key) or []), *value]))
            elif isinstance(value, str) and existing.get(key):
                if value and value != existing[key]:
                    existing[key] = f"{existing[key]}\n[CON] {value}"
            else:
                existing[key] = value
        data["current_assumptions"] = existing

    if update.research_suggestions is not None:
        seen = {s.direction for s in view.research_suggestions}
        merged = list(view.research_suggestions)
        for item in update.research_suggestions:
            if item.direction and item.direction not in seen:
                merged.append(item)
                seen.add(item.direction)
        data["research_suggestions"] = [s.model_dump() for s in merged]

    if update.research_directions is not None:
        data["research_directions"] = list(
            dict.fromkeys([*(view.research_directions or []), *update.research_directions])
        )

    if update.dimension_coverage is not None:
        coverage = dict(view.dimension_coverage)
        for dim, status in update.dimension_coverage.items():
            coverage[dim] = _merge_coverage(coverage.get(dim), status)
        data["dimension_coverage"] = {k: v.value if hasattr(v, "value") else v for k, v in coverage.items()}

    if update.coverage_score is not None:
        data["coverage_score"] = max(view.coverage_score, update.coverage_score)

    if update.source_doc_ids is not None:
        data["source_doc_ids"] = list(dict.fromkeys([*view.source_doc_ids, *update.source_doc_ids]))

    return AssumptionView.model_validate(data)
