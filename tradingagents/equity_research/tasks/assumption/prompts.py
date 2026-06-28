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
from tradingagents.equity_research.state.consensus_schemas import CoverageStatus
from tradingagents.equity_research.tasks.assumption.schemas import (
    ASSUMPTION_DIMENSIONS,
    AssumptionView,
    empty_assumption_view,
)
from tradingagents.equity_research.tasks.consensus.compliance import COMPLIANCE_QUERY_SUFFIX
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
        f"- Business model: {view.current_assumptions.business_model[:300]}",
        f"- Market sentiment: {view.current_assumptions.market_sentiment[:200]}",
        f"- Key debates: {', '.join(view.current_assumptions.key_debates[:5])}",
        f"- Research directions: {', '.join(view.research_directions[:5])}",
    ]
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
        "Choose skill names from the catalog only. Return at most two skill names."
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
    consensus_text = compact_if_needed(
        deps, _consensus_context(state), purpose="consensus for assumption planning",
    )
    return (
        f"Generate an initial Perplexity search query queue to probe key assumptions "
        f"behind market consensus on {ticker}.\n\n"
        f"Market consensus view:\n{consensus_text}\n\n"
        f"Active skills:\n{format_skill_names(skill_ctx.get('names', []))}\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{memory_block}\n"
        f"{COMPLIANCE_QUERY_SUFFIX}\n\n"
        "Produce 3-5 query items covering assumption themes. Each item must include:\n"
        "- query: 10-80 English words\n"
        f"- target_dimension: one of\n{format_dimension_list(ASSUMPTION_DIMENSIONS)}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer (higher = run first)\n"
        "Do not repeat queries already in prior search memory."
    )


def build_loop_planner_prompt(deps: Any, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    report = state.get("coverage_report", {})
    skill_ctx = state.get("active_skill_context", {})
    search_memory = state.get("search_memory", [])
    executed = queries_from_memory(search_memory) or state.get("executed_queries", [])
    view = _parse_view(state)
    view_text = compact_if_needed(deps, format_assumption_view(view), purpose="assumption view for gap planning")
    consensus_text = compact_if_needed(
        deps, _consensus_context(state), purpose="consensus for assumption loop planning",
    )

    return (
        f"Generate up to 2 new Perplexity queries to fill assumption gaps for {ticker}.\n"
        f"Last coverage evaluation (round {state.get('iterations', 0)}):\n"
        f"{format_coverage_report_for_planner(report, state)}\n\n"
        f"Market consensus:\n{consensus_text}\n\n"
        f"Current assumption view:\n{view_text}\n\n"
        f"Prior search memory:\n{build_search_memory_for_prompt(deps, search_memory)}\n"
        f"Executed queries:\n{format_executed_queries(executed)}\n\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{COMPLIANCE_QUERY_SUFFIX}\n\n"
        "Produce up to 2 query items. Prioritize weak assumption dimensions.\n"
        f"- target_dimension: one of\n{format_dimension_list(ASSUMPTION_DIMENSIONS)}\n"
    )


def build_synthesizer_prompt(deps: Any, state: dict[str, Any], view: AssumptionView, pending: list) -> str:
    ticker = state.get("ticker", "")
    view_text = compact_if_needed(deps, format_assumption_view(view), purpose="assumption view")
    consensus_text = compact_if_needed(
        deps, _consensus_context(state), purpose="consensus for assumption synthesis",
    )
    evidence_text = build_search_memory_for_prompt(deps, pending, max_chars=None)
    if not evidence_text or evidence_text == "- No prior searches recorded.":
        evidence_text = format_search_memory(pending)
    return (
        f"Update the assumption research view for {ticker} using new search evidence.\n\n"
        f"Market consensus (read-only context):\n{consensus_text}\n\n"
        f"Current assumption view:\n{view_text}\n\n"
        f"New search evidence (this round only):\n{evidence_text}\n\n"
        "Merge incrementally. Populate current_assumptions from evidence only.\n"
        "Add research_suggestions (direction, rationale, priority, related_assumption).\n"
        "Add concise research_directions titles (list of strings).\n"
        "Label unverified claims [UNVERIFIED]. Keep conflicts with [CON].\n"
        "Update dimension_coverage for probed assumption dimensions."
    )


def build_reflector_prompt(deps: Any, view: AssumptionView, memory_summary: str) -> str:
    view_text = compact_if_needed(
        deps, format_assumption_view(view), purpose="assumption view for coverage evaluation",
    )
    return (
        f"Evaluate coverage of assumption probing for {view.ticker}.\n"
        f"Assumption view:\n{view_text}\n"
        f"{memory_summary}\n"
        "Score each assumption dimension as empty, partial, sufficient, or strong.\n"
        "Provide an overall_score between 0 and 1.\n"
        "List critical_gaps as dimension names still weak.\n"
        "List suggested_focus as dimensions to prioritize next."
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
        f"(target 400-800 words, max {report_max_chars} characters).\n\n"
        f"Consensus report excerpt:\n{str(consensus_report)[:1500]}\n\n"
        f"Structured assumption view:\n{view_text}\n\n"
        f"Coverage evaluation:\n{coverage}\n\n"
        f"Search memory summary:\n{memory_text}\n\n"
        f"Active skills context:\n{format_skill_context(skill_ctx)}\n\n"
        "Include:\n"
        "- Key assumptions behind consensus\n"
        "- Research suggestions and directions for follow-up work\n"
        "- Data gaps and recommended next checks"
    )


def default_coverage_report(view: AssumptionView) -> CoverageReport:
    from tradingagents.equity_research.state.consensus_schemas import CoverageReport

    scores = {dim: CoverageStatus.EMPTY for dim in ASSUMPTION_DIMENSIONS}
    for dim, status in (view.dimension_coverage or {}).items():
        if dim in scores:
            scores[dim] = status if isinstance(status, CoverageStatus) else CoverageStatus(str(status))
    return CoverageReport(
        dimension_scores=scores,
        overall_score=view.coverage_score,
        critical_gaps=[d for d, s in scores.items() if s in (CoverageStatus.EMPTY, CoverageStatus.PARTIAL)],
        suggested_focus=list(ASSUMPTION_DIMENSIONS[:3]),
    )


def evaluation_to_report(evaluation) -> CoverageReport:
    from tradingagents.equity_research.state.consensus_schemas import CoverageReport

    return CoverageReport(
        dimension_scores=evaluation.dimension_scores,
        overall_score=evaluation.overall_score,
        critical_gaps=evaluation.critical_gaps,
        suggested_focus=evaluation.suggested_focus,
    )


def apply_evidence_heuristic(view: AssumptionView, pending: list) -> None:
    if not pending:
        return
    citations: list[str] = []
    for item in pending:
        citations.extend(item.get("citations") or [])
    if citations and not view.current_assumptions.sources:
        view.current_assumptions.sources = list(dict.fromkeys(citations))[:20]
    if pending and not view.research_directions:
        dims = [p.get("target_dimension", "") for p in pending if p.get("target_dimension")]
        view.research_directions = list(dict.fromkeys(dims))[:5]
