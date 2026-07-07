"""Orthogonal memory search tools — one retrieval axis per function."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.memory.retrieval import build_memory_context


def _result(tool: str, items: list[dict[str, Any]], **meta: Any) -> dict[str, Any]:
    return {"tool": tool, "count": len(items), "items": items, **meta}


def search_evidence(
    state: dict[str, Any],
    query: str = "",
    *,
    metric: str = "",
    max_items: int = 10,
    deps: Any = None,
) -> dict[str, Any]:
    """Semantic search over evidence ledger (quote + metric)."""
    filters: dict[str, Any] = {"ledger_types": ["evidence"]}
    if metric:
        filters["metric"] = metric
    ctx = build_memory_context(
        state,
        [],
        {"priority_questions": [query]} if query else {},
        max_items=max(max_items * 2, 10),
        filters=filters,
        deps=deps,
    )
    items = ctx.get("evidence", [])[:max_items]
    return _result("search_evidence", items, query=query, metric=metric or None)


def search_claims(
    state: dict[str, Any],
    query: str = "",
    *,
    section_id: str = "",
    metric: str = "",
    confidence_min: float | None = None,
    confidence_max: float | None = None,
    max_items: int = 10,
    deps: Any = None,
) -> dict[str, Any]:
    """Structured search over claim ledger (section, confidence, metric)."""
    filters: dict[str, Any] = {"ledger_types": ["claim"]}
    if section_id:
        filters["section_id"] = section_id
    if metric:
        filters["metric"] = metric
    if confidence_min is not None:
        filters["confidence_min"] = confidence_min
    if confidence_max is not None:
        filters["confidence_max"] = confidence_max
    ctx = build_memory_context(
        state,
        [],
        {"priority_questions": [query]} if query else {},
        max_items=max(max_items * 2, 10),
        filters=filters,
        deps=deps,
    )
    items = ctx.get("claims", [])[:max_items]
    return _result(
        "search_claims",
        items,
        query=query or None,
        section_id=section_id or None,
        metric=metric or None,
    )


def search_assumptions(
    state: dict[str, Any],
    query: str = "",
    *,
    metric: str = "",
    sensitivity: str = "",
    max_items: int = 10,
    deps: Any = None,
) -> dict[str, Any]:
    """Search model assumptions by metric and sensitivity."""
    filters: dict[str, Any] = {"ledger_types": ["assumption"]}
    if metric:
        filters["metric"] = metric
    if sensitivity:
        filters["sensitivity"] = sensitivity
    ctx = build_memory_context(
        state,
        [],
        {"priority_questions": [query]} if query else {},
        max_items=max(max_items * 2, 10),
        filters=filters,
        deps=deps,
    )
    items = ctx.get("assumptions", [])[:max_items]
    return _result(
        "search_assumptions",
        items,
        query=query or None,
        metric=metric or None,
        sensitivity=sensitivity or None,
    )


def search_consensus(
    state: dict[str, Any],
    query: str = "",
    *,
    metric: str = "",
    max_items: int = 5,
    deps: Any = None,
) -> dict[str, Any]:
    """Search consensus ledger entries."""
    filters: dict[str, Any] = {"ledger_types": ["consensus"]}
    if metric:
        filters["metric"] = metric
    ctx = build_memory_context(
        state,
        [],
        {"priority_questions": [query]} if query else {},
        max_items=max(max_items * 2, 6),
        filters=filters,
        deps=deps,
    )
    items = ctx.get("consensus", [])[:max_items]
    return _result("search_consensus", items, query=query or None, metric=metric or None)


def search_conflicts(
    state: dict[str, Any],
    *,
    metric: str = "",
) -> dict[str, Any]:
    """List open memory conflicts and contradictory evidence fragments."""
    conflicts = list(state.get("memory_conflicts", []))
    fragments = list(state.get("contradiction_fragments", []))
    if metric:
        needle = metric.lower()
        conflicts = [c for c in conflicts if needle in str(c.get("metric", "")).lower()]
        fragments = [f for f in fragments if needle in str(f.get("metric", "")).lower()]
    return {
        "tool": "search_conflicts",
        "metric": metric or None,
        "open_conflicts": len(conflicts),
        "conflicts": conflicts,
        "contradiction_fragments": fragments,
    }


def search_memory_timeline(
    state: dict[str, Any],
    *,
    last_n: int = 5,
) -> dict[str, Any]:
    """Return recent iteration snapshots for temporal trend analysis."""
    snapshots = list(state.get("iteration_snapshots", []))
    if last_n > 0:
        snapshots = snapshots[-last_n:]
    return {
        "tool": "search_memory_timeline",
        "research_iteration": int(state.get("research_iterations", 0)),
        "count": len(snapshots),
        "snapshots": snapshots,
    }


def search_research_context(
    state: dict[str, Any],
    query: str = "",
    *,
    parent_nodes: list[str] | None = None,
    max_items: int = 20,
    deps: Any = None,
) -> dict[str, Any]:
    """Holistic research context bundle for prompt injection (all ledger types)."""
    ctx = build_memory_context(
        state,
        parent_nodes or [],
        {"priority_questions": [query]} if query else {},
        max_items=max_items,
        deps=deps,
    )
    return {"tool": "search_research_context", **ctx}
