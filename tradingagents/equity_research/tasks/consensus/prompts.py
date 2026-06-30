"""Consensus-specific prompt builders and view formatting."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.runtime.utils.context_compact import compact_if_needed
from tradingagents.equity_research.runtime.utils.prompt_helpers import (
    format_coverage_report_for_planner,
    format_dimension_list,
    format_executed_queries,
    format_skill_context,
    format_skill_names,
)
from tradingagents.equity_research.runtime.utils.search_memory import (
    build_search_memory_for_prompt,
    format_search_memory,
    queries_from_memory,
)
from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    CoverageReport,
    CoverageStatus,
    QueryItem,
    SearchMode,
    StructuredConsensusView,
    empty_structured_consensus_view,
)
from tradingagents.equity_research.tasks.consensus.compliance import (
    COMPLIANCE_QUERY_SUFFIX,
    PUBLIC_DATA_SOURCE_NOTE,
    append_compliance_suffix,
)


def _status_label(status: CoverageStatus | str | None) -> str:
    if isinstance(status, CoverageStatus):
        return status.value
    return str(status or "empty")


def _format_sources(sources: list[str]) -> list[str]:
    if not sources:
        return ["    - (none)"]
    return [f"    - {url}" for url in sources]


def format_consensus_view(view: StructuredConsensusView) -> str:
    lines: list[str] = [f"**Consensus view**"]
    lines: list[str] = [f"- Ticker: {view.ticker}", f"- Coverage score: {view.coverage_score}"]
    qe = view.quantitative_estimates
    lines.append("- Quantitative estimates:")
    lines.append(f"  - Analyst count: {qe.analyst_count}")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('quantitative_estimates'))}")
    # lines.append("  - Sources:")
    # lines.extend(_format_sources(qe.sources))

    kpi = view.kpi_focus
    lines.append("- KPI focus:")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('kpi_focus'))}")
    for item in kpi.primary_kpis[:5]:
        lines.append(f"  - KPI: {item.name} — expected {item.expected_level} ({item.importance})")
    # lines.append("  - Sources:")
    # lines.extend(_format_sources(kpi.sources))

    pa = view.pricing_assumptions
    lines.append("- Pricing assumptions:")
    lines.append(f"  - Implied growth: {pa.implied_growth_rate}")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('pricing_assumptions'))}")
    for peer in pa.peer_comparison[:3]:
        lines.append(f"  - Peer {peer.ticker}: {peer.metric} = {peer.value} ({peer.comparison})")
    # lines.append("  - Sources:")
    # lines.extend(_format_sources(pa.sources))

    nf = view.narrative_framework
    lines.append("- Narrative framework:")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('narrative_framework'))}")
    if nf.bull_case:
        lines.append(f"  - Bull case: {nf.bull_case[:400]}")
    if nf.bear_case:
        lines.append(f"  - Bear case: {nf.bear_case[:400]}")
    for debate in nf.key_debates[:5]:
        lines.append(f"  - Debate: {debate}")
    # lines.append("  - Sources:")
    # lines.extend(_format_sources(nf.sources))

    rd = view.recent_delta
    lines.append("- Recent delta:")
    lines.append(f"  - Coverage: {_status_label(view.dimension_coverage.get('recent_delta'))}")
    if rd.estimate_revisions:
        lines.append(f"  - Estimate revisions: {rd.estimate_revisions[:300]}")
    if rd.guidance_change:
        lines.append(f"  - Guidance change: {rd.guidance_change[:300]}")
    if rd.sentiment_shift:
        lines.append(f"  - Sentiment shift: {rd.sentiment_shift[:300]}")
    # lines.append("  - Sources:")
    # lines.extend(_format_sources(rd.sources))
    return "\n".join(lines)


def _parse_view(state: dict[str, Any]) -> StructuredConsensusView:
    ticker = state.get("ticker", "")
    raw = state.get("structured_view") or state.get("consensus_view") or {}
    if raw:
        return StructuredConsensusView.model_validate(raw)
    return empty_structured_consensus_view(ticker)


def build_skill_prompt(state: dict[str, Any], catalog_table: str, ticker: str) -> str:
    return (
        f"Select equity research skills to load for building market consensus on {ticker}.\n"
        f"Sector: {state.get('sector', '')}\n"
        f"Report type: {state.get('report_type', '')}\n"
        f"Instrument context: {state.get('instrument_context', '')[:500]}\n\n"
        f"Skill catalog (read descriptions and when_to_use before deciding):\n{catalog_table}\n\n"
        "Choose skill names from the catalog only.\n"
        "You may return an empty load_skills list if no skill is needed.\n"
        "Return at most two skill names."
    )


def build_initial_planner_prompt(deps: Any, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    skill_ctx = state.get("active_skill_context", {})
    search_memory = state.get("search_memory", [])
    memory_block = ""
    if search_memory:
        memory_block = (
            f"\nPrior search memory:\n"
            f"{build_search_memory_for_prompt(deps, search_memory)}\n"
        )
    return (
        f"Generate an initial Perplexity search query queue for market consensus on {ticker}.\n"
        f"Sector: {state.get('sector', '')}\n"
        f"Report type: {state.get('report_type', '')}\n"
        f"Active skills:\n{format_skill_names(skill_ctx.get('names', []))}\n\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{memory_block}\n"
        f"{PUBLIC_DATA_SOURCE_NOTE}\n\n"
        "Produce exactly 5 query items, one for each dimension. Each item must include:\n"
        "- query: 10-80 English words targeting public sources only (no FactSet, Bloomberg Terminal, or Refinitiv)\n"
        f"- target_dimension: one of\n{format_dimension_list(CONSENSUS_DIMENSIONS)}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer (higher = run first)\n\n"
        "Do not repeat queries already covered in prior search memory."
    )


def build_loop_planner_prompt(deps: Any, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    report = state.get("coverage_report", {})
    skill_ctx = state.get("active_skill_context", {})
    search_memory = state.get("search_memory", [])
    executed = queries_from_memory(search_memory) or state.get("executed_queries", [])
    view = _parse_view(state)
    view_text = compact_if_needed(deps, format_consensus_view(view), purpose="consensus view for gap planning")

    human_history = state.get("human_followup_history") or []
    human_block = ""
    if human_history:
        human_block = (
            "\nAnalyst follow-up requests (most recent last):\n"
            + "\n".join(f"- {q}" for q in human_history[-3:])
            + "\n"
        )

    return (
        f"Generate up to 2 new Perplexity queries to find consensus gaps in the view for {ticker}.\n"
        f"Last coverage evaluation (round {state.get('iterations', 0)}):\n"
        f"{format_coverage_report_for_planner(report, state)}\n\n"
        f"Current consensus view:\n{view_text}\n\n"
        f"Prior search memory:\n{build_search_memory_for_prompt(deps, search_memory)}\n"
        f"Executed queries:\n{format_executed_queries(executed)}\n\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{human_block}\n"
        f"{PUBLIC_DATA_SOURCE_NOTE}\n\n"
        "Produce a query plan with up to 2 items. Each item must include:\n"
        "- query: 10-80 English words, different from prior queries; public sources only "
        "(no FactSet, Bloomberg Terminal, or Refinitiv)\n"
        f"- target_dimension: one of\n{format_dimension_list(CONSENSUS_DIMENSIONS)}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer\n"
        "Prioritize dimensions still weak per the coverage evaluation above.\n"
        "Do not re-search topics already sufficient or strong.\n"
        "Do not repeat topics already covered in prior search memory.\n"
        "If quantitative_estimates is partial due to source_quality limits on public data, "
        "do not generate queries for paid terminal databases; focus on other weak dimensions.\n"
        "If there is any conflicts between existing content and new evidence, "
        "record conflicts structurally; do not rely on [CON] text markers.\n"
    )


_ASSUMPTION_THEMES = (
    ("business_model", "How does this company make money?"),
    ("market_sentiment", "Is the market bullish or bearish and why?"),
    ("key_metrics", "Which KPIs do investors focus on?"),
    ("valuation", "Why is the valuation high or low?"),
    ("earnings_focus", "What matters most in upcoming earnings?"),
    ("expectation_changes", "Have expectations changed recently?"),
    ("benchmark_expectations", "What is the market benchmark expectation?"),
    ("model_drivers", "What variables do sell-side models hinge on?"),
    ("debates", "What are the key debates?"),
    ("stress_test", "Which assumptions deserve stress testing?"),
    ("next_data", "What data should be checked next?"),
)


def build_assumption_planner_prompt(deps: Any, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    view = _parse_view(state)
    view_text = compact_if_needed(deps, format_consensus_view(view), purpose="consensus view for assumption probe")
    themes = "\n".join(f"- {theme}: {question}" for theme, question in _ASSUMPTION_THEMES)
    report = state.get("coverage_report", {})
    search_memory = state.get("search_memory", [])

    return (
        f"Generate 3-5 Perplexity search queries to probe key assumptions behind "
        f"market consensus on {ticker}.\n\n"
        f"Current consensus view:\n{view_text}\n\n"
        f"Coverage summary:\n{format_coverage_report_for_planner(report, state)}\n\n"
        f"Prior search memory:\n{build_search_memory_for_prompt(deps, search_memory)}\n\n"
        f"Probe themes (prioritize gaps, not every theme needs a query):\n{themes}\n\n"
        f"{PUBLIC_DATA_SOURCE_NOTE}\n"
        f"{COMPLIANCE_QUERY_SUFFIX}\n\n"
        "Each query item must include:\n"
        "- query: 10-80 English words with compliance suffix if not already present\n"
        f"- target_dimension: one of\n{format_dimension_list(CONSENSUS_DIMENSIONS)}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer (higher = run first)\n"
        "Map each query to the most relevant dimension."
    )


def normalize_assumption_queries(
    items: list[QueryItem],
    ticker: str,
    use_default_if_empty: bool,
) -> list[QueryItem]:
    from tradingagents.equity_research.tasks.consensus.queries import normalize_query_items

    normalized = normalize_query_items(items, ticker, use_default_if_empty=False)
    result: list[QueryItem] = []
    for item in normalized:
        result.append(
            QueryItem(
                query=append_compliance_suffix(item.query),
                target_dimension=item.target_dimension,
                mode=item.mode,
                priority=item.priority,
            )
        )
    if result:
        return result[:5]
    if use_default_if_empty:
        return [
            QueryItem(
                query=append_compliance_suffix(
                    f"{ticker} how does the company make money revenue model margins"
                ),
                target_dimension="narrative_framework",
                mode=SearchMode.EXPLORATORY,
                priority=5,
            ),
            QueryItem(
                query=append_compliance_suffix(
                    f"{ticker} market sentiment bull bear analyst rating consensus"
                ),
                target_dimension="narrative_framework",
                mode=SearchMode.EXPLORATORY,
                priority=4,
            ),
            QueryItem(
                query=append_compliance_suffix(
                    f"{ticker} key KPI metrics investors watch earnings focus"
                ),
                target_dimension="kpi_focus",
                mode=SearchMode.TARGETED,
                priority=3,
            ),
        ]
    return []


def build_synthesizer_prompt(deps: Any, state: dict[str, Any], view: StructuredConsensusView, pending: list) -> str:
    ticker = state.get("ticker", "")
    view_text = compact_if_needed(deps, format_consensus_view(view), purpose="consensus view")
    evidence_text = build_search_memory_for_prompt(deps, pending, max_chars=None)
    if not evidence_text or evidence_text == "- No prior searches recorded.":
        evidence_text = format_search_memory(pending)
    return (
        f"Update the structured consensus view for {ticker} using search evidence.\n"
        f"Current view:\n{view_text}\n\n"
        f"New search evidence (this round only):\n{evidence_text}\n\n"
        "Merge incrementally — do not erase existing content.\n"
        "If there is any conflict between existing content and new evidence, "
        "add a structured conflict record (claim_a, claim_b, interpretation) in conflicts; "
        "do not append [CON] tags to field text.\n"
        "Attribute evidence only to its target_dimension.\n"
        "Update dimension_coverage for each dimension.\n"
        "For every numeric estimate include period, period_end, estimate_type, basis, and source_quality when known.\n"
        "If evidence comes from public aggregators or news rather than paid terminals, still populate "
        "quantitative_estimates with available fields and label source_quality accordingly; "
        "do not leave the dimension empty solely due to missing terminal-grade precision.\n"
        "Do not use Reddit, YouTube, or social media as core estimate evidence.\n"
        "Do not fabricate numbers without citation in sources."
    )


def build_reflector_prompt(deps: Any, view: StructuredConsensusView, memory_summary: str) -> str:
    view_text = compact_if_needed(
        deps, format_consensus_view(view), purpose="consensus view for coverage evaluation",
    )
    return (
        f"Evaluate coverage of the consensus view for {view.ticker}.\n"
        f"View:\n{view_text}\n"
        f"{memory_summary}\n"
        "Score each dimension as empty, partial, sufficient, or strong.\n"
        "Also assess source_quality across dimensions (reliability of citations, period clarity).\n"
        "For quantitative_estimates: distinguish missing content from source_quality limits. "
        "If public-source evidence exists (aggregator/media/secondary) but terminal-grade precision "
        "is unavailable, score partial or sufficient and do NOT list quantitative_estimates in "
        "critical_gaps solely due to paid-database access limits.\n"
        "If the only remaining weaknesses are quantitative_estimates and/or source_quality, "
        "list those explicitly; the loop will exit rather than re-query paid terminals.\n"
        "Provide an overall_score between 0 and 1.\n"
        "List critical_gaps as dimension names still weak.\n"
        "List suggested_focus as dimensions to prioritize next."
    )


def build_assumption_synth_prompt(deps: Any, view: StructuredConsensusView, evidence_text: str) -> str:
    view_text = compact_if_needed(
        deps, format_consensus_view(view), purpose="consensus view for assumption synthesis",
    )
    return (
        f"Extract key assumptions behind market consensus for {view.ticker}.\n"
        f"Current view:\n{view_text}\n\n"
        f"Assumption probe evidence:\n{evidence_text}\n\n"
        "Populate all ConsensusAssumptions fields from evidence only.\n"
        "Label claims without public citation as [UNVERIFIED].\n"
        "If evidence conflicts, keep both views and label [CON].\n"
        "Collect all citation URLs in sources."
    )


def build_finalizer_prompt(deps: Any, ctx: dict[str, Any]) -> str:
    state = ctx["state"]
    view = ctx["view"]
    assumptions = ctx["assumptions"]
    coverage = ctx["coverage"]
    search_memory = ctx["search_memory"]
    skill_ctx = ctx["skill_ctx"]
    compliance_flags = ctx["compliance_flags"]
    report_max_chars = ctx["report_max_chars"]
    ticker = state.get("ticker", "")

    view_text = compact_if_needed(deps, format_consensus_view(view), purpose="consensus final report")
    memory_text = build_search_memory_for_prompt(deps, search_memory) if search_memory else ""
    compliance_text = ""
    if compliance_flags:
        compliance_text = (
            "\nCompliance flags:\n"
            + "\n".join(
                f"- [{f.get('type', 'flag')}] {f.get('message', '')}"
                for f in compliance_flags[:10]
            )
        )

    return (
        f"Write a moderate-length market consensus report for {ticker} "
        f"(target 800-1500 words, aim for roughly {report_max_chars} characters).\n\n"
        f"Structured consensus view:\n{view_text}\n\n"
        f"Key assumptions behind consensus:\n{assumptions}\n\n"
        f"Coverage evaluation:\n{coverage}\n\n"
        f"Search memory summary:\n{memory_text}\n\n"
        f"Active skills context:\n{format_skill_context(skill_ctx)}\n"
        f"{compliance_text}\n\n"
        "Requirements:\n"
        "- Organize by the five consensus dimensions\n"
        "- Include a section titled 'Key Assumptions Behind Consensus'\n"
        "- Note evidence gaps explicitly\n"
        "- Include key citation URLs inline\n"
        "- Do not fabricate numbers without sources\n"
        "- Disclose any compliance flags at the end\n"
        "Return markdown only."
    )


def _status_score(status: CoverageStatus) -> float:
    return {
        CoverageStatus.EMPTY: 0.0,
        CoverageStatus.PARTIAL: 0.4,
        CoverageStatus.SUFFICIENT: 0.75,
        CoverageStatus.STRONG: 1.0,
    }.get(status, 0.0)


def _upgrade_coverage(current: CoverageStatus, evidence_count: int, citation_count: int) -> CoverageStatus:
    if evidence_count >= 3 and citation_count >= 3:
        return CoverageStatus.SUFFICIENT
    if evidence_count >= 1 or citation_count >= 1:
        return CoverageStatus.PARTIAL
    return current


def default_coverage_report(view: StructuredConsensusView) -> CoverageReport:
    scores: dict[str, CoverageStatus] = {}
    for dim in CONSENSUS_DIMENSIONS:
        scores[dim] = view.dimension_coverage.get(dim, CoverageStatus.EMPTY)
    numeric = [_status_score(s) for s in scores.values()]
    overall = sum(numeric) / len(numeric) if numeric else 0.0
    critical = [d for d, s in scores.items() if s in (CoverageStatus.EMPTY, CoverageStatus.PARTIAL)]
    return CoverageReport(
        dimension_scores=scores,
        overall_score=overall,
        critical_gaps=critical,
        suggested_focus=critical[:2],
        routing_decision="exit" if overall >= 0.75 and not critical else "continue",
    )


def evaluation_to_report(evaluation: Any) -> CoverageReport:
    dim_scores: dict[str, CoverageStatus] = {}
    for dim in CONSENSUS_DIMENSIONS:
        dim_scores[dim] = evaluation.dimension_scores.get(dim, CoverageStatus.EMPTY)
    return CoverageReport(
        dimension_scores=dim_scores,
        overall_score=evaluation.overall_score,
        critical_gaps=list(evaluation.critical_gaps),
        suggested_focus=list(evaluation.suggested_focus),
    )


def _quantitative_estimates_has_public_evidence(view: StructuredConsensusView) -> bool:
    qe = view.quantitative_estimates
    if qe.sources or qe.analyst_count:
        return True
    for field_name in ("revenue_estimates", "earnings_estimates", "fcf_estimates"):
        estimate_range = getattr(qe, field_name, None)
        if not estimate_range:
            continue
        for year_key in ("year_1", "year_2", "year_3"):
            year_est = getattr(estimate_range, year_key, None)
            if year_est and any(
                getattr(year_est, attr, "")
                for attr in ("low", "median", "high", "period", "source_quality")
            ):
                return True
    return False


def apply_consensus_reflector_guards(
    view: StructuredConsensusView,
    report: CoverageReport,
) -> CoverageReport:
    if "quantitative_estimates" not in report.critical_gaps:
        return report
    if not _quantitative_estimates_has_public_evidence(view):
        return report
    score = report.dimension_scores.get("quantitative_estimates", CoverageStatus.EMPTY)
    if score in (
        CoverageStatus.PARTIAL,
        CoverageStatus.SUFFICIENT,
        CoverageStatus.STRONG,
    ):
        report.critical_gaps = [
            gap for gap in report.critical_gaps if gap != "quantitative_estimates"
        ]
    return report


def apply_evidence_heuristic(view: StructuredConsensusView, evidence: list[dict]) -> None:
    dim_evidence: dict[str, list[dict]] = {dim: [] for dim in CONSENSUS_DIMENSIONS}
    for ev in evidence:
        dim = ev.get("target_dimension", "")
        if dim in dim_evidence:
            dim_evidence[dim].append(ev)

    for dim, items in dim_evidence.items():
        if not items:
            continue
        citation_count = sum(len(ev.get("citations") or []) for ev in items)
        answer_len = sum(len(ev.get("answer", "")) for ev in items)
        current = view.dimension_coverage.get(dim, CoverageStatus.EMPTY)
        if len(items) >= 3 and citation_count >= 3 and answer_len > 800:
            status = CoverageStatus.SUFFICIENT
        elif citation_count >= 1 or answer_len > 0:
            status = _upgrade_coverage(current, len(items), citation_count)
        else:
            status = current

        for ev in items:
            answer = ev.get("answer", "")
            sources = ev.get("citations", [])
            if dim == "quantitative_estimates":
                view.quantitative_estimates.sources.extend(sources)
            elif dim == "kpi_focus":
                view.kpi_focus.sources.extend(sources)
            elif dim == "pricing_assumptions":
                view.pricing_assumptions.sources.extend(sources)
            elif dim == "narrative_framework":
                if not view.narrative_framework.bull_case and answer:
                    view.narrative_framework.bull_case = answer[:500]
                view.narrative_framework.sources.extend(sources)
            elif dim == "recent_delta":
                if not view.recent_delta.estimate_revisions and answer:
                    view.recent_delta.estimate_revisions = answer[:500]
                view.recent_delta.sources.extend(sources)
        view.dimension_coverage[dim] = status

    from tradingagents.equity_research.tasks.consensus.merge import preserve_citations_from_evidence
    preserve_citations_from_evidence(view, evidence)
