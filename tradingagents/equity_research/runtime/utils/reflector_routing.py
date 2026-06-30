"""Reflector routing helpers for research subgraphs."""

from __future__ import annotations

from typing import Any

TERMINAL_LIMITED_GAP_LABELS = frozenset({"quantitative_estimates", "source_quality"})


def gaps_are_only_terminal_limited(
    critical_gaps: list[str] | None,
    *,
    suggested_focus: list[str] | None = None,
    allowed: frozenset[str] | None = None,
) -> bool:
    """True when reflector issues are exclusively terminal/source-quality limited."""
    allowed = allowed or TERMINAL_LIMITED_GAP_LABELS
    issues = {gap for gap in (critical_gaps or []) if gap}
    issues.update(gap for gap in (suggested_focus or []) if gap)
    if not issues:
        return False
    return issues <= allowed


def should_force_exit_on_terminal_gaps(
    report: Any,
    *,
    allowed: frozenset[str] | None = None,
) -> bool:
    return gaps_are_only_terminal_limited(
        list(getattr(report, "critical_gaps", None) or []),
        suggested_focus=list(getattr(report, "suggested_focus", None) or []),
        allowed=allowed,
    )
