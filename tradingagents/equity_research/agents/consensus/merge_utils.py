"""Nested merge utilities for structured consensus view updates."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.state.consensus_schemas import (
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


def _merge_scalar(old: Any, new: Any) -> Any:
    if not old:
        return new
    if not new:
        return old
    if old == new:
        return old
    return f"{old}\n[CON] {new}"


def _merge_list(old: list[Any] | None, new: list[Any] | None) -> list[Any]:
    combined = [*(old or []), *(new or [])]
    if not combined:
        return []
    if all(isinstance(item, str) for item in combined):
        return _dedupe_preserve_order(combined)
    return combined


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


def _merge_dict(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(old or {})
    for key, value in (new or {}).items():
        if key not in merged or not merged[key]:
            merged[key] = value
        elif isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _merge_dict(merged[key], value)
        elif isinstance(merged[key], list) and isinstance(value, list):
            merged[key] = _merge_list(merged[key], value)
        else:
            merged[key] = _merge_scalar(merged[key], value)
    return merged


def _merge_model_dict(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    merged = dict(old)
    for key, value in new.items():
        if value is None:
            continue
        if key == "sources" and isinstance(value, list):
            merged[key] = _merge_list(merged.get(key, []), value)
        elif key == "dimension_coverage" and isinstance(value, dict):
            existing = merged.get(key, {})
            coverage_merged = dict(existing)
            for dim, status in value.items():
                coverage_merged[dim] = _merge_coverage(existing.get(dim), status)
            merged[key] = coverage_merged
        elif isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge_model_dict(merged[key], value)
        elif isinstance(value, list) and isinstance(merged.get(key), list):
            merged[key] = _merge_list(merged.get(key, []), value)
        elif isinstance(value, str):
            merged[key] = _merge_scalar(merged.get(key, ""), value)
        else:
            if not merged.get(key):
                merged[key] = value
    return merged


def merge_view_update(view: StructuredConsensusView, update: Any) -> StructuredConsensusView:
    merged = _merge_model_dict(view.model_dump(), update.model_dump(exclude_none=True))
    merged["ticker"] = view.ticker or update.ticker
    if update.dimension_coverage:
        for dim, status in update.dimension_coverage.items():
            merged.setdefault("dimension_coverage", {})[dim] = _merge_coverage(
                view.dimension_coverage.get(dim),
                status,
            )
    return StructuredConsensusView.model_validate(merged)
