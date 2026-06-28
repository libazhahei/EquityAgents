"""Generic prompt formatting helpers for research subgraphs."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.runtime.utils.search_memory import (
    format_search_memory,
    queries_from_memory,
)


def format_skill_names(skills: list[str]) -> str:
    if not skills:
        return "- No active skills loaded."
    return "\n".join(f"- {name}" for name in skills)


def format_skill_context(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    constraints = ctx.get("constraints", "")
    guidance = ctx.get("query_guidance", "")
    prompt_template = ctx.get("prompt_template", "")
    if constraints:
        parts.append("Constraints:")
        parts.append(constraints)
    if guidance:
        parts.append("Query guidance:")
        parts.append(guidance)
    if prompt_template:
        parts.append("Skill prompt guidance:")
        parts.append(prompt_template)
    return "\n\n".join(parts) if parts else "- No skill context."


def format_dimension_list(dimensions: tuple[str, ...] | list[str]) -> str:
    return "\n".join(f"- {dim}" for dim in dimensions)


def format_executed_queries(
    queries: list[str] | None = None,
    *,
    search_memory: list[dict] | None = None,
) -> str:
    items = queries or queries_from_memory(search_memory or [])
    if not items:
        return "- No queries executed yet."
    return "\n".join(f"- {q}" for q in items)


def format_coverage_gaps(report: dict[str, Any]) -> str:
    critical = report.get("critical_gaps", [])
    focus = report.get("suggested_focus", [])
    lines = ["- Critical gaps:"]
    lines.extend(f"  - {gap}" for gap in critical) if critical else lines.append("  - (none)")
    lines.append("- Suggested focus:")
    lines.extend(f"  - {item}" for item in focus) if focus else lines.append("  - (none)")
    return "\n".join(lines)


def format_coverage_report_for_planner(
    report: dict[str, Any],
    state: dict[str, Any],
    *,
    dimensions: tuple[str, ...] | list[str] | None = None,
) -> str:
    iteration = int(state.get("iterations", state.get("consensus_iterations", 0)))
    max_iter = int(state.get("max_iterations", state.get("max_consensus_iterations", 5)))
    overall = report.get("overall_score", 0.0)
    routing = report.get("routing_decision", "continue")
    dim_scores = report.get("dimension_scores", {})

    lines = [
        f"- Round: {iteration} / {max_iter}",
        f"- Overall score: {overall}",
        "- Dimension scores:",
    ]
    if dim_scores:
        for dim, status in dim_scores.items():
            label = status.value if hasattr(status, "value") else str(status)
            lines.append(f"  - {dim}: {label}")
    else:
        lines.append("  - (none)")
    lines.append(format_coverage_gaps(report))
    lines.append(f"- Routing: {routing}")
    return "\n".join(lines)


def format_evidence_batch(evidence: list[dict]) -> str:
    return format_search_memory(evidence)
