"""Bullet-list prompt formatting for consensus subgraph LLM nodes."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.consensus.search_memory import (
    format_search_memory,
    queries_from_memory,
)
from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    CoverageStatus,
    StructuredConsensusView,
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


def _status_label(status: CoverageStatus | str | None) -> str:
    if isinstance(status, CoverageStatus):
        return status.value
    return str(status or "empty")


def _format_sources(sources: list[str]) -> list[str]:
    if not sources:
        return ["    - (none)"]
    return [f"    - {url}" for url in sources]


def format_consensus_view(view: StructuredConsensusView) -> str:
    lines: list[str] = [f"- Ticker: {view.ticker}", f"- Coverage score: {view.coverage_score}"]
    qe = view.quantitative_estimates
    lines.append("- Quantitative estimates:")
    lines.append(f"  - Analyst count: {qe.analyst_count}")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('quantitative_estimates'))}")
    lines.append("  - Sources:")
    lines.extend(_format_sources(qe.sources))

    kpi = view.kpi_focus
    lines.append("- KPI focus:")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('kpi_focus'))}")
    for item in kpi.primary_kpis[:5]:
        lines.append(f"  - KPI: {item.name} — expected {item.expected_level} ({item.importance})")
    lines.append("  - Sources:")
    lines.extend(_format_sources(kpi.sources))

    pa = view.pricing_assumptions
    lines.append("- Pricing assumptions:")
    lines.append(f"  - Implied growth: {pa.implied_growth_rate}")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('pricing_assumptions'))}")
    for peer in pa.peer_comparison[:3]:
        lines.append(f"  - Peer {peer.ticker}: {peer.metric} = {peer.value} ({peer.comparison})")
    lines.append("  - Sources:")
    lines.extend(_format_sources(pa.sources))

    nf = view.narrative_framework
    lines.append("- Narrative framework:")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('narrative_framework'))}")
    if nf.bull_case:
        lines.append(f"  - Bull case: {nf.bull_case[:400]}")
    if nf.bear_case:
        lines.append(f"  - Bear case: {nf.bear_case[:400]}")
    for debate in nf.key_debates[:5]:
        lines.append(f"  - Debate: {debate}")
    lines.append("  - Sources:")
    lines.extend(_format_sources(nf.sources))

    rd = view.recent_delta
    lines.append("- Recent delta:")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('recent_delta'))}")
    if rd.estimate_revisions:
        lines.append(f"  - Estimate revisions: {rd.estimate_revisions[:300]}")
    if rd.guidance_change:
        lines.append(f"  - Guidance change: {rd.guidance_change[:300]}")
    if rd.sentiment_shift:
        lines.append(f"  - Sentiment shift: {rd.sentiment_shift[:300]}")
    lines.append("  - Sources:")
    lines.extend(_format_sources(rd.sources))
    return "\n".join(lines)


def format_evidence_batch(evidence: list[dict]) -> str:
    return format_search_memory(evidence)


def format_coverage_gaps(report: dict[str, Any]) -> str:
    critical = report.get("critical_gaps", [])
    focus = report.get("suggested_focus", [])
    lines = ["- Critical gaps:"]
    lines.extend(f"  - {gap}" for gap in critical) if critical else lines.append("  - (none)")
    lines.append("- Suggested focus:")
    lines.extend(f"  - {item}" for item in focus) if focus else lines.append("  - (none)")
    return "\n".join(lines)


def format_coverage_report_for_planner(report: dict[str, Any], state: dict[str, Any]) -> str:
    iteration = int(state.get("consensus_iterations", 0))
    max_iter = int(state.get("max_consensus_iterations", 5))
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
            lines.append(f"  - {dim}: {_status_label(status)}")
    else:
        lines.append("  - (none)")
    lines.append(format_coverage_gaps(report))
    lines.append(f"- Routing: {routing}")
    return "\n".join(lines)


def format_executed_queries(
    queries: list[str] | None = None,
    *,
    search_memory: list[dict] | None = None,
) -> str:
    items = queries or queries_from_memory(search_memory or [])
    if not items:
        return "- No queries executed yet."
    return "\n".join(f"- {q}" for q in items)


def format_dimension_list() -> str:
    return "\n".join(f"- {dim}" for dim in CONSENSUS_DIMENSIONS)
