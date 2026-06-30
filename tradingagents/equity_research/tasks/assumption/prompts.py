"""Assumption task prompt builders."""

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
from tradingagents.equity_research.state.consensus_schemas import CoverageReport, CoverageStatus
from tradingagents.equity_research.tasks.assumption.schemas import (
    ASSUMPTION_QUALITY_DIMENSIONS,
    ASSUMPTION_SEARCH_DIMENSIONS,
    AssumptionView,
    empty_assumption_view,
)
from tradingagents.equity_research.tasks.consensus.compliance import (
    COMPLIANCE_QUERY_SUFFIX,
    PUBLIC_DATA_SOURCE_NOTE,
)
from tradingagents.equity_research.tasks.consensus.prompts import format_consensus_view


def _consensus_context(state: dict[str, Any]) -> str:
    parent = state.get("parent_context") or {}
    raw = parent.get("consensus_view") or state.get("consensus_view") or {}
    if not raw:
        return "No consensus view available."
    try:
        from tradingagents.equity_research.state.consensus_schemas import StructuredConsensusView
        view = StructuredConsensusView.model_validate(raw)
        return format_consensus_view(view)
    except Exception:
        return str(raw)[:6000]


def _dedupe_memory_block(deps: Any, search_memory: list) -> str:
    if not search_memory:
        return ""
    return (
        "\nAlready searched topics (for deduplication only — do not summarize these records):\n"
        f"{build_search_memory_for_prompt(deps, search_memory)}\n"
    )


def _parse_view(state: dict[str, Any]) -> AssumptionView:
    ticker = state.get("ticker", "")
    raw = state.get("structured_view") or {}
    if raw:
        return AssumptionView.model_validate(raw)
    return empty_assumption_view(ticker)


def format_assumption_view(view: AssumptionView) -> str:
    lines = [
        f"- Ticker: {view.ticker}",
        f"- Coverage score: {view.coverage_score}",
        f"- Assumption items: {len(view.assumption_map)}",
        f"- Research priorities: {', '.join(view.top_research_priorities[:5])}",
    ]
    for item in view.assumption_map[:8]:
        lines.append(f"- [{item.id or '?'}] ({item.category}) {item.statement[:280]}")
        if item.consensus_anchor:
            lines.append(f"  anchor: {item.consensus_anchor[:200]}")
        if item.falsification_tests:
            lines.append(f"  falsification: {item.falsification_tests[0][:160]}")
    for suggestion in view.research_suggestions[:5]:
        lines.append(f"- Suggestion: {suggestion.direction} — {suggestion.rationale[:200]}")
    return "\n".join(lines)


def build_skill_prompt(state: dict[str, Any], catalog_table: str, ticker: str) -> str:
    return (
        f"Select equity research skills to probe assumptions behind market consensus on {ticker}.\n"
        f"Sector: {state.get('sector', '')}\n"
        f"Report type: {state.get('report_type', '')}\n"
        f"Consensus context excerpt:\n{_consensus_context(state)[:800]}\n\n"
        f"Skill catalog:\n{catalog_table}\n\n"
        "Choose skill names from the catalog only. Return at most two skill names.\n"
        "Do not select broker_consensus_mining for assumption probing."
    )


def build_initial_planner_prompt(deps: Any, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    skill_ctx = state.get("active_skill_context", {})
    search_memory = state.get("search_memory", [])
    memory_block = _dedupe_memory_block(deps, search_memory)
    consensus_text = compact_if_needed(
        deps, _consensus_context(state), purpose="consensus for assumption planning",
    )
    return (
        f"Generate an initial Perplexity search query queue to probe key implicit assumptions "
        f"behind market consensus on {ticker}.\n\n"
        f"Market consensus view (read-only anchor — do not restate in queries):\n{consensus_text}\n\n"
        f"Active skills:\n{format_skill_names(skill_ctx.get('names', []))}\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{memory_block}\n"
        f"{PUBLIC_DATA_SOURCE_NOTE}\n"
        f"{COMPLIANCE_QUERY_SUFFIX}\n\n"
        "Produce 3-5 query items probing hidden assumptions. Each item must include:\n"
        "- query: 10-80 English words focused on what the market must be assuming; public sources only "
        "(no FactSet, Bloomberg Terminal, or Refinitiv)\n"
        f"- target_dimension: one of\n{format_dimension_list(ASSUMPTION_SEARCH_DIMENSIONS)}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer (higher = run first)\n"
        "Do not search for business overviews, analyst ratings, or consensus estimate tables."
    )


def build_loop_planner_prompt(deps: Any, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    report = state.get("coverage_report", {})
    skill_ctx = state.get("active_skill_context", {})
    search_memory = state.get("search_memory", [])
    executed = queries_from_memory(search_memory) or state.get("executed_queries", [])
    view = _parse_view(state)
    view_text = compact_if_needed(deps, format_assumption_view(view), purpose="assumption view for gap planning")

    return (
        f"Generate up to 2 new Perplexity queries to fill assumption gaps for {ticker}.\n"
        f"Last coverage evaluation (round {state.get('iterations', 0)}):\n"
        f"{format_coverage_report_for_planner(report, state, dimensions=ASSUMPTION_QUALITY_DIMENSIONS)}\n\n"
        f"Current assumption view:\n{view_text}\n\n"
        f"{_dedupe_memory_block(deps, search_memory)}"
        f"Executed queries:\n{format_executed_queries(executed)}\n\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{PUBLIC_DATA_SOURCE_NOTE}\n"
        f"{COMPLIANCE_QUERY_SUFFIX}\n\n"
        "Produce up to 2 query items. Prioritize weak assumption quality dimensions.\n"
        "Use public sources only; do not query paid terminals (FactSet, Bloomberg, Refinitiv).\n"
        f"- target_dimension: one of\n{format_dimension_list(ASSUMPTION_SEARCH_DIMENSIONS)}\n"
    )


_SYNTHESIZER_RULES = """
Do NOT produce a consensus summary.
Do NOT restate business model, market sentiment, KPI lists, valuation multiples, or recent estimate changes.
Use the consensus view only to infer implicit assumptions.

Infer the implicit assumptions that must be true for the consensus view to hold.
Every assumption must be phrased as: "The market is implicitly assuming that ..."

For each assumption item include:
- id, statement, category, consensus_anchor, model_drivers
- evidence_for, evidence_against
- confidence, controversy_level, model_sensitivity
- falsification_tests, next_data_to_watch

If a claim is merely a consensus fact, convert it into an explicit implicit assumption or omit it.
Do not embed [UNVERIFIED] or [CON] in statement text; use structured fields instead.
Add research_suggestions and top_research_priorities for follow-up work.
"""


def build_synthesizer_prompt(deps: Any, state: dict[str, Any], view: AssumptionView, pending: list) -> str:
    view_text = compact_if_needed(deps, format_assumption_view(view), purpose="assumption view")
    consensus_text = compact_if_needed(
        deps, _consensus_context(state), purpose="consensus for assumption synthesis",
    )
    evidence_text = build_search_memory_for_prompt(deps, pending, max_chars=None)
    if not evidence_text or evidence_text == "- No prior searches recorded.":
        evidence_text = format_search_memory(pending)
    return (
        f"Update the assumption research view for {state.get('ticker', '')} using new search evidence.\n\n"
        f"Market consensus (read-only anchor):\n{consensus_text}\n\n"
        f"Current assumption view:\n{view_text}\n\n"
        f"New search evidence (this round only):\n{evidence_text}\n\n"
        f"{_SYNTHESIZER_RULES}\n"
        "Merge incrementally into assumption_map. Update dimension_coverage for quality dimensions."
    )


def build_reflector_prompt(deps: Any, view: AssumptionView, memory_summary: str) -> str:
    view_text = compact_if_needed(
        deps, format_assumption_view(view), purpose="assumption view for coverage evaluation",
    )
    return (
        f"Evaluate whether the output is a true assumption map, not a consensus summary for {view.ticker}.\n"
        f"Assumption view:\n{view_text}\n"
        f"{memory_summary}\n"
        "Score each quality dimension as empty, partial, sufficient, or strong:\n"
        f"{format_dimension_list(ASSUMPTION_QUALITY_DIMENSIONS)}\n"
        "Provide an overall_score between 0 and 1.\n"
        "List critical_gaps when:\n"
        "- output restates consensus instead of inferring assumptions (over_summarizes_consensus)\n"
        "- fewer than 3 assumptions have falsification_tests (missing_falsification_tests)\n"
        "- assumptions lack model_drivers (missing_model_linkage)\n"
        "- excessive duplicate suggestions (poor_deduplication)\n"
        "List suggested_focus as quality dimensions to prioritize next."
    )


def build_finalizer_prompt(deps: Any, ctx: dict[str, Any]) -> str:
    state = ctx["state"]
    view = ctx["view"]
    coverage = ctx["coverage"]
    search_memory = ctx["search_memory"]
    skill_ctx = ctx["skill_ctx"]
    report_max_chars = ctx["report_max_chars"]
    ticker = state.get("ticker", "")
    consensus_report = (state.get("parent_context") or {}).get("consensus_report", "")

    view_text = compact_if_needed(deps, format_assumption_view(view), purpose="assumption final report")
    memory_text = build_search_memory_for_prompt(deps, search_memory) if search_memory else ""

    return (
        f"Write a concise assumption probe report for {ticker} "
        f"(target 400-800 words, aim for roughly {report_max_chars} characters).\n\n"
        f"Consensus report excerpt (context only — do not summarize again):\n{str(consensus_report)[:1500]}\n\n"
        f"Structured assumption map:\n{view_text}\n\n"
        f"Coverage evaluation:\n{coverage}\n\n"
        f"Assumption search memory summary:\n{memory_text}\n\n"
        f"Active skills context:\n{format_skill_context(skill_ctx)}\n\n"
        "Include:\n"
        "- Key implicit assumptions (not consensus recap)\n"
        "- Falsification tests and next data to watch per major assumption\n"
        "- Research suggestions and top priorities\n"
        "- Data gaps and recommended next checks"
    )


def default_coverage_report(view: AssumptionView) -> CoverageReport:
    scores = {dim: CoverageStatus.EMPTY for dim in ASSUMPTION_QUALITY_DIMENSIONS}
    for dim, status in (view.dimension_coverage or {}).items():
        if dim in scores:
            scores[dim] = status if isinstance(status, CoverageStatus) else CoverageStatus(str(status))
    return CoverageReport(
        dimension_scores=scores,
        overall_score=view.coverage_score,
        critical_gaps=_compute_critical_gaps(view),
        suggested_focus=list(ASSUMPTION_QUALITY_DIMENSIONS[:3]),
    )


def _compute_critical_gaps(view: AssumptionView) -> list[str]:
    gaps: list[str] = []
    if not view.assumption_map:
        gaps.append("missing_assumptions")
        return gaps

    consensus_like = sum(
        1 for item in view.assumption_map
        if not item.statement.lower().startswith("the market is implicitly assuming")
    )
    if consensus_like > max(1, len(view.assumption_map) * 0.3):
        gaps.append("over_summarizes_consensus")

    with_falsification = sum(1 for item in view.assumption_map if item.falsification_tests)
    if with_falsification < 3:
        gaps.append("missing_falsification_tests")

    without_drivers = sum(1 for item in view.assumption_map if not item.model_drivers)
    if without_drivers > len(view.assumption_map) // 2:
        gaps.append("missing_model_linkage")

    directions = [s.direction for s in view.research_suggestions if s.direction]
    if len(directions) != len(set(directions)):
        gaps.append("poor_deduplication")

    return gaps


def apply_reflector_guards(view: AssumptionView, report: CoverageReport) -> CoverageReport:
    gaps = list(dict.fromkeys([*report.critical_gaps, *_compute_critical_gaps(view)]))
    report.critical_gaps = gaps
    if gaps and report.overall_score > 0.85:
        report.overall_score = min(report.overall_score, 0.75)
    return report


def evaluation_to_report(evaluation) -> CoverageReport:
    report = CoverageReport(
        dimension_scores=evaluation.dimension_scores,
        overall_score=evaluation.overall_score,
        critical_gaps=evaluation.critical_gaps,
        suggested_focus=evaluation.suggested_focus,
    )
    return report


def apply_evidence_heuristic(view: AssumptionView, pending: list) -> None:
    if not pending:
        return
    from tradingagents.equity_research.tasks.assumption.schemas import AssumptionItem

    citations: list[str] = []
    for item in pending:
        citations.extend(item.get("citations") or [])
    next_id = len(view.assumption_map) + 1
    for ev in pending[:3]:
        dim = ev.get("target_dimension", "demand_assumptions")
        answer = str(ev.get("answer", ""))[:400]
        if not answer:
            continue
        view.assumption_map.append(
            AssumptionItem(
                id=f"A{next_id}",
                statement=f"The market is implicitly assuming that {answer[:200]}",
                category=dim,
                consensus_anchor="Derived from search evidence pending linkage",
                evidence_for=[answer[:300]],
                source_doc_ids=list(ev.get("doc_ids") or []),
            )
        )
        next_id += 1
    if citations and not view.source_doc_ids:
        view.source_doc_ids = list(dict.fromkeys(citations))[:20]
    if pending and not view.top_research_priorities:
        dims = [p.get("target_dimension", "") for p in pending if p.get("target_dimension")]
        view.top_research_priorities = list(dict.fromkeys(dims))[:5]
