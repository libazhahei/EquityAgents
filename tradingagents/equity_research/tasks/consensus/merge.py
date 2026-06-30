"""Nested merge utilities for structured consensus view updates."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.runtime.utils.dedupe import merge_list_by_similarity
from tradingagents.equity_research.state.consensus_schemas import (
    ConflictRecord,
    CoverageStatus,
    StructuredConsensusView,
)


_COVERAGE_ORDER = {
    CoverageStatus.EMPTY: 0,
    CoverageStatus.PARTIAL: 1,
    CoverageStatus.SUFFICIENT: 2,
    CoverageStatus.STRONG: 3,
}


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _merge_scalar(old: Any, new: Any, *, conflicts: list[ConflictRecord] | None = None) -> Any:
    if not old:
        return new
    if not new:
        return old
    if old == new:
        return old
    if conflicts is not None:
        conflicts.append(
            ConflictRecord(
                claim_a=str(old)[:500],
                claim_b=str(new)[:500],
                interpretation="Conflicting values merged as structured conflict",
                resolution_status="unresolved",
            )
        )
    return old


def _merge_string_list(
    old: list[Any] | None,
    new: list[Any] | None,
    *,
    semantic: bool = True,
) -> list[Any]:
    combined = [*(old or []), *(new or [])]
    if not combined:
        return []
    if all(isinstance(item, str) for item in combined):
        if semantic:
            return merge_list_by_similarity(list(old or []), list(new or []))
        return _dedupe_preserve_order(combined)
    return combined


def _merge_list(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    return _merge_string_list(old, new, semantic=True)


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


def _merge_model_dict(old: dict[str, Any], new: dict[str, Any], conflicts: list[ConflictRecord]) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if value is None:
            continue
        if key == "sources" and isinstance(value, list):
            merged[key] = _merge_string_list(merged.get(key, []), value, semantic=False)
        elif key == "conflicts" and isinstance(value, list):
            merged[key] = _merge_list(merged.get(key, []), value)
        elif key == "dimension_coverage" and isinstance(value, dict):
            existing = merged.get(key, {})
            coverage_merged = dict(existing)
            for dim, status in value.items():
                coverage_merged[dim] = _merge_coverage(existing.get(dim), status)
            merged[key] = coverage_merged
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_model_dict(merged[key], value, conflicts)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = _merge_list(merged.get(key, []), value)
        elif isinstance(value, str):
            merged[key] = _merge_scalar(merged.get(key, ""), value, conflicts=conflicts)
        else:
            if not merged.get(key):
                merged[key] = value
    return merged


def merge_view_update(view: StructuredConsensusView, update: Any) -> StructuredConsensusView:
    conflicts: list[ConflictRecord] = list(view.conflicts)
    merged = _merge_model_dict(view.model_dump(), update.model_dump(exclude_none=True), conflicts)
    if update.conflicts:
        conflicts.extend(update.conflicts)
    merged["conflicts"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in conflicts]
    merged["ticker"] = view.ticker or update.ticker
    if update.dimension_coverage:
        for dim, status in update.dimension_coverage.items():
            merged.setdefault("dimension_coverage", {})[dim] = _merge_coverage(
                view.dimension_coverage.get(dim),
                status,
            )
    return StructuredConsensusView.model_validate(merged)


def dedupe_preserve_order(items: list[str]) -> list[str]:
    return _dedupe_preserve_order(items)


def preserve_citations_from_evidence(view: StructuredConsensusView, evidence: list[dict]) -> None:
    dim_sources: dict[str, list[str]] = {
        "quantitative_estimates": view.quantitative_estimates.sources,
        "kpi_focus": view.kpi_focus.sources,
        "pricing_assumptions": view.pricing_assumptions.sources,
        "narrative_framework": view.narrative_framework.sources,
        "recent_delta": view.recent_delta.sources,
    }
    all_doc_ids = list(view.source_doc_ids)
    for ev in evidence:
        dim = ev.get("target_dimension", "")
        citations = ev.get("citations") or []
        if dim in dim_sources:
            dim_sources[dim].extend(citations)
        all_doc_ids.extend(ev.get("doc_ids", []))
    for sources in dim_sources.values():
        deduped = _dedupe_preserve_order(sources)
        sources.clear()
        sources.extend(deduped)
    view.source_doc_ids = _dedupe_preserve_order(all_doc_ids)


def preserve_citations_from_memory(view: StructuredConsensusView, records: list[dict]) -> None:
    dim_sources: dict[str, list[str]] = {
        "quantitative_estimates": view.quantitative_estimates.sources,
        "kpi_focus": view.kpi_focus.sources,
        "pricing_assumptions": view.pricing_assumptions.sources,
        "narrative_framework": view.narrative_framework.sources,
        "recent_delta": view.recent_delta.sources,
    }
    all_doc_ids = list(view.source_doc_ids)
    for record in records:
        dim = record.get("target_dimension", "")
        citations = record.get("citations") or []
        if dim in dim_sources:
            dim_sources[dim].extend(citations)
        all_doc_ids.extend(record.get("doc_ids", []))
    for sources in dim_sources.values():
        deduped = _dedupe_preserve_order(sources)
        sources.clear()
        sources.extend(deduped)
    view.source_doc_ids = _dedupe_preserve_order(all_doc_ids)
