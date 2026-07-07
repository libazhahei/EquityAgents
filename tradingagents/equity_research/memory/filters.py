"""Filter schema for multidimensional memory retrieval."""

from __future__ import annotations

from typing import Any, TypedDict


class MemoryFilters(TypedDict, total=False):
    parent_nodes: list[str]
    metric: str
    section_id: str
    confidence_min: float
    confidence_max: float
    sensitivity: str
    ledger_types: list[str]
    tags: list[str]
    status: str


def apply_memory_filters(
    entries: list[dict[str, Any]],
    filters: MemoryFilters | dict[str, Any] | None,
    *,
    ledger_kind: str,
) -> list[dict[str, Any]]:
    if not filters:
        return entries
    result = entries
    status = filters.get("status")
    if status:
        result = [e for e in result if e.get("status", "active") == status]
    elif ledger_kind == "evidence":
        result = [e for e in result if e.get("status", "active") not in {"archived", "merged"}]

    metric = filters.get("metric")
    if metric:
        needle = metric.lower()
        if ledger_kind == "claim":
            result = [e for e in result if needle in str(e.get("claim", "")).lower() or needle in str(e.get("metric", "")).lower()]
        elif ledger_kind == "assumption":
            result = [e for e in result if needle in str(e.get("metric", "")).lower()]
        else:
            result = [e for e in result if needle in str(e.get("metric", "")).lower() or needle in str(e.get("quote", "")).lower()]

    section_id = filters.get("section_id")
    if section_id and ledger_kind == "claim":
        result = [e for e in result if e.get("section_id") == section_id]

    confidence_min = filters.get("confidence_min")
    if confidence_min is not None and ledger_kind == "claim":
        result = [e for e in result if float(e.get("confidence", 0.0)) >= float(confidence_min)]

    confidence_max = filters.get("confidence_max")
    if confidence_max is not None and ledger_kind == "claim":
        result = [e for e in result if float(e.get("confidence", 0.0)) <= float(confidence_max)]

    sensitivity = filters.get("sensitivity")
    if sensitivity and ledger_kind == "assumption":
        result = [e for e in result if str(e.get("sensitivity", "")).lower() == sensitivity.lower()]

    tags = filters.get("tags")
    if tags:
        tag_set = {t.lower() for t in tags}
        result = [
            e for e in result
            if tag_set.intersection({str(t).lower() for t in e.get("tags", [])})
        ]

    return result
