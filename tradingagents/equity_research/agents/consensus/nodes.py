"""Consensus subgraph node factories."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.consensus.compliance import (
    COMPLIANCE_QUERY_SUFFIX,
    append_compliance_suffix,
    check_assumption_evidence_compliance,
    filter_compliant_citations,
)
from tradingagents.equity_research.agents.consensus.context_compact import compact_if_needed
from tradingagents.equity_research.agents.consensus.merge_utils import merge_view_update
from tradingagents.equity_research.agents.consensus.prompt_format import (
    format_consensus_view,
    format_coverage_report_for_planner,
    format_dimension_list,
    format_executed_queries,
    format_skill_context,
    format_skill_names,
)
from tradingagents.equity_research.agents.consensus.search_memory import (
    build_search_memory_for_prompt,
    format_search_memory,
    queries_from_memory,
)
from tradingagents.equity_research.agents.consensus.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.shared.query_planner import create_query_planner_node
from tradingagents.equity_research.agents.shared.search_executor import create_search_batch_executor
from tradingagents.equity_research.agents.shared.skill_selector import (
    create_skill_context_apply,
    create_skill_selector as _shared_create_skill_selector,
    create_skill_selector_agent,
    create_skill_tools_node,
)
from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    ConsensusAssumptions,
    ConsensusViewUpdate,
    CoverageEvaluation,
    CoverageReport,
    CoverageStatus,
    QueryItem,
    QueryPlan,
    SearchMode,
    StructuredConsensusView,
    empty_structured_consensus_view,
)


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _default_queries(ticker: str) -> list[QueryItem]:
    return [
        QueryItem(
            query=f"{ticker} analyst consensus revenue estimates next 3 years range median",
            target_dimension="quantitative_estimates",
            mode=SearchMode.TARGETED,
            priority=5,
        ),
        QueryItem(
            query=f"{ticker} key metrics analysts watch most important KPIs earnings call",
            target_dimension="kpi_focus",
            mode=SearchMode.EXPLORATORY,
            priority=4,
        ),
        QueryItem(
            query=f"{ticker} forward PE EV EBITDA multiple implied growth vs peers",
            target_dimension="pricing_assumptions",
            mode=SearchMode.TARGETED,
            priority=3,
        ),
        QueryItem(
            query=f"{ticker} bull case bear case investment thesis debate",
            target_dimension="narrative_framework",
            mode=SearchMode.EXPLORATORY,
            priority=2,
        ),
        QueryItem(
            query=f"{ticker} estimate revision after earnings guidance change recent",
            target_dimension="recent_delta",
            mode=SearchMode.TARGETED,
            priority=1,
        ),
    ]


def _normalize_query_items(
    items: list[QueryItem],
    ticker: str,
    use_default_if_empty: bool,
) -> list[QueryItem]:
    normalized: list[QueryItem] = []
    for item in items:
        dim = item.target_dimension
        if dim not in CONSENSUS_DIMENSIONS:
            dim = "narrative_framework"
        normalized.append(
            QueryItem(
                query=str(item.query)[:500],
                target_dimension=dim,
                mode=item.mode,
                priority=item.priority,
            )
        )
    if normalized:
        return normalized
    return _default_queries(ticker) if use_default_if_empty else []


def _status_score(status: CoverageStatus) -> float:
    return {
        CoverageStatus.EMPTY: 0.0,
        CoverageStatus.PARTIAL: 0.4,
        CoverageStatus.SUFFICIENT: 0.75,
        CoverageStatus.STRONG: 1.0,
    }.get(status, 0.0)


def _upgrade_coverage(
    current: CoverageStatus,
    evidence_count: int,
    citation_count: int,
) -> CoverageStatus:
    if evidence_count >= 3 and citation_count >= 3:
        return CoverageStatus.SUFFICIENT
    if evidence_count >= 1 or citation_count >= 1:
        return CoverageStatus.PARTIAL
    return current


def _default_coverage_report(view: StructuredConsensusView) -> CoverageReport:
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


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _preserve_citations_from_evidence(view: StructuredConsensusView, evidence: list[dict]) -> None:
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


def _preserve_citations_from_memory(view: StructuredConsensusView, records: list[dict]) -> None:
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


def _apply_evidence_heuristic(view: StructuredConsensusView, evidence: list[dict]) -> None:
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

    _preserve_citations_from_evidence(view, evidence)


def _evaluation_to_report(evaluation: CoverageEvaluation) -> CoverageReport:
    dim_scores: dict[str, CoverageStatus] = {}
    for dim in CONSENSUS_DIMENSIONS:
        dim_scores[dim] = evaluation.dimension_scores.get(dim, CoverageStatus.EMPTY)
    return CoverageReport(
        dimension_scores=dim_scores,
        overall_score=evaluation.overall_score,
        critical_gaps=list(evaluation.critical_gaps),
        suggested_focus=list(evaluation.suggested_focus),
    )


def _consensus_skill_prompt(state: dict[str, Any], catalog_table: str, ticker: str) -> str:
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


def create_consensus_skill_selector(deps: EquityResearchDeps):
    return _shared_create_skill_selector(
        deps,
        graph_name="consensus_subgraph",
        objective="consensus",
        max_skills=2,
        trace_name="consensus_skill_selector",
        prompt_builder=_consensus_skill_prompt,
    )


def create_consensus_skill_selector_agent(deps: EquityResearchDeps):
    return create_skill_selector_agent(
        deps,
        graph_name="consensus_subgraph",
        objective="consensus",
        max_skills=2,
        prompt_builder=_consensus_skill_prompt,
    )


def create_consensus_skill_tools(deps: EquityResearchDeps):
    return create_skill_tools_node(
        deps,
        graph_name="consensus_subgraph",
        objective="consensus",
        max_skills=2,
    )


def create_consensus_skill_context_apply(deps: EquityResearchDeps):
    return create_skill_context_apply(
        deps,
        graph_name="consensus_subgraph",
        objective="consensus",
        max_skills=2,
        trace_name="consensus_skill_selector",
    )


# Backward-compatible alias
create_skill_selector = create_consensus_skill_selector


def create_initial_query_planner(deps: EquityResearchDeps):
    def prompt_builder(state: dict[str, Any]) -> str:
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
            f"Active skills:\n{format_skill_names(skill_ctx.get('names', []))}\n"
            f"{format_skill_context(skill_ctx)}\n"
            f"{memory_block}\n"
            "Produce exactly 5 query items, one for each dimension. Each item must include:\n"
            "- query: 10-80 English words\n"
            f"- target_dimension: one of\n{format_dimension_list()}\n"
            "- mode: exploratory or targeted\n"
            "- priority: integer (higher = run first)\n"
            "Do not repeat queries already covered in prior search memory."
        )

    def fallback_plan(state: dict[str, Any]) -> QueryPlan:
        return QueryPlan(queries=_default_queries(state.get("ticker", "")))

    return create_query_planner_node(
        deps,
        prompt_builder=prompt_builder,
        max_queries=5,
        use_default_if_empty=True,
        normalize_fn=_normalize_query_items,
        agent_name="consensus_planner",
        trace_name="consensus_planner",
        fallback_plan=fallback_plan,
        extend_queue=False,
    )


# Backward-compatible alias
create_consensus_planner = create_initial_query_planner


def _gap_planner_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    report = state.get("coverage_report", {})
    skill_ctx = state.get("active_skill_context", {})
    search_memory = state.get("search_memory", [])
    executed = queries_from_memory(search_memory) or state.get("executed_queries", [])

    raw_view = state.get("consensus_view") or {}
    if raw_view:
        view = StructuredConsensusView.model_validate(raw_view)
    else:
        view = empty_structured_consensus_view(ticker)

    view_text = compact_if_needed(
        deps,
        format_consensus_view(view),
        purpose="consensus view for gap planning",
    )

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
        f"Last coverage evaluation (round {state.get('consensus_iterations', 0)}):\n"
        f"{format_coverage_report_for_planner(report, state)}\n\n"
        f"Current consensus view:\n{view_text}\n\n"
        f"Prior search memory:\n{build_search_memory_for_prompt(deps, search_memory)}\n"
        f"Executed queries:\n{format_executed_queries(executed)}\n\n"
        f"{format_skill_context(skill_ctx)}\n"
        f"{human_block}\n"
        "Produce a query plan with up to 2 items. Each item must include:\n"
        "- query: 10-80 English words, different from prior queries\n"
        f"- target_dimension: one of\n{format_dimension_list()}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer\n"
        "Prioritize dimensions still weak per the coverage evaluation above.\n"
        "Do not re-search topics already sufficient or strong.\n"
        "Do not repeat topics already covered in prior search memory.\n"
        "If there is any conflicts between existing content and new evidence, leave both side view.\n"
    )


def create_loop_query_planner(deps: EquityResearchDeps):
    return create_query_planner_node(
        deps,
        prompt_builder=lambda state: _gap_planner_prompt(deps, state),
        max_queries=2,
        use_default_if_empty=False,
        normalize_fn=_normalize_query_items,
        agent_name="consensus_query_planner",
        trace_name="consensus_query_planner",
        executed_queries_fn=lambda state: (
            queries_from_memory(state.get("search_memory", []))
            or state.get("executed_queries", [])
        ),
        extend_queue=True,
    )


# Backward-compatible alias
create_query_planner = create_loop_query_planner


def create_query_batch_executor(deps: EquityResearchDeps, *, batch_size: int = 5):
    return create_search_batch_executor(
        deps,
        batch_size=batch_size,
        trace_name="consensus_query_executor",
    )


# Backward-compatible alias (batch_size=1 for single-query behavior in tests)
create_query_executor = lambda deps: create_query_batch_executor(deps, batch_size=1)


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


def _assumption_planner_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    ticker = state.get("ticker", "")
    raw_view = state.get("consensus_view") or {}
    if raw_view:
        view = StructuredConsensusView.model_validate(raw_view)
    else:
        view = empty_structured_consensus_view(ticker)

    view_text = compact_if_needed(
        deps,
        format_consensus_view(view),
        purpose="consensus view for assumption probe",
    )
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
        f"{COMPLIANCE_QUERY_SUFFIX}\n\n"
        "Each query item must include:\n"
        "- query: 10-80 English words with compliance suffix if not already present\n"
        f"- target_dimension: one of\n{format_dimension_list()}\n"
        "- mode: exploratory or targeted\n"
        "- priority: integer (higher = run first)\n"
        "Map each query to the most relevant dimension."
    )


def _normalize_assumption_queries(
    items: list[QueryItem],
    ticker: str,
    use_default_if_empty: bool,
) -> list[QueryItem]:
    normalized = _normalize_query_items(items, ticker, use_default_if_empty=False)
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


def create_assumption_probe_gate(deps: EquityResearchDeps):
    def assumption_probe_gate(state: dict[str, Any]) -> dict[str, Any]:
        return {}

    return assumption_probe_gate


def create_assumption_query_planner(deps: EquityResearchDeps):
    return create_query_planner_node(
        deps,
        prompt_builder=lambda state: _assumption_planner_prompt(deps, state),
        max_queries=5,
        use_default_if_empty=True,
        normalize_fn=_normalize_assumption_queries,
        agent_name="assumption_query_planner",
        trace_name="assumption_query_planner",
        extend_queue=False,
    )


def create_assumption_batch_executor(deps: EquityResearchDeps):
    base_executor = create_search_batch_executor(
        deps,
        batch_size=5,
        trace_name="assumption_probe_executor",
    )

    def assumption_batch_executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base_executor(state)
        if not result:
            return {"assumption_pending_evidence": list(state.get("pending_evidence", []))}

        pending = list(result.get("pending_evidence", []))
        flags = list(state.get("compliance_flags", []))
        cleaned_pending: list[dict] = []

        for item in pending:
            item_dict = dict(item)
            citations = list(item_dict.get("citations") or [])
            kept, item_flags = filter_compliant_citations(
                citations,
                config=deps.config,
            )
            item_dict["citations"] = kept
            item_dict["compliance_checked"] = True
            cleaned_pending.append(item_dict)
            flags.extend(item_flags)

        result["pending_evidence"] = cleaned_pending
        result["assumption_pending_evidence"] = cleaned_pending
        result["compliance_flags"] = flags
        return result

    return assumption_batch_executor


def create_assumption_synthesizer(deps: EquityResearchDeps):
    def assumption_synthesizer(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        pending = list(
            state.get("assumption_pending_evidence")
            or state.get("pending_evidence", [])
        )
        try:
            raw_view = state.get("consensus_view") or {}
            if raw_view:
                view = StructuredConsensusView.model_validate(raw_view)
            else:
                view = empty_structured_consensus_view(ticker)

            assumptions = ConsensusAssumptions()
            if pending:
                view_text = compact_if_needed(
                    deps,
                    format_consensus_view(view),
                    purpose="consensus view for assumption synthesis",
                )
                evidence_text = build_search_memory_for_prompt(deps, pending, max_chars=None)
                if not evidence_text or evidence_text == "- No prior searches recorded.":
                    evidence_text = format_search_memory(pending)

                prompt = (
                    f"Extract key assumptions behind market consensus for {ticker}.\n"
                    f"Current view:\n{view_text}\n\n"
                    f"Assumption probe evidence:\n{evidence_text}\n\n"
                    "Populate all ConsensusAssumptions fields from evidence only.\n"
                    "Label claims without public citation as [UNVERIFIED].\n"
                    "If evidence conflicts, keep both views and label [CON].\n"
                    "Collect all citation URLs in sources."
                )

                def _fallback() -> ConsensusAssumptions:
                    return ConsensusAssumptions(
                        business_model=view.narrative_framework.bull_case[:500],
                        key_debates=list(view.narrative_framework.key_debates),
                        sources=_dedupe_preserve_order(
                            sum((ev.get("citations") or [] for ev in pending), [])
                        ),
                    )

                try:
                    assumptions = invoke_structured_with_retry(
                        deps.quick_llm,
                        ConsensusAssumptions,
                        prompt,
                        agent_name="assumption_synthesizer",
                        max_attempts=_max_retries(deps),
                        fallback=_fallback,
                    )
                except StructuredOutputUnsupported:
                    assumptions = _fallback()

            flags = list(state.get("compliance_flags", []))
            flags.extend(
                check_assumption_evidence_compliance(
                    pending,
                    assumptions.model_dump(),
                    config=deps.config,
                )
            )

            updates: dict[str, Any] = {
                "consensus_assumptions": assumptions.model_dump(),
                "assumption_probe_completed": True,
                "assumption_pending_evidence": [],
                "pending_evidence": [],
                "compliance_flags": flags,
            }
            updates.update(deps.trace({**state, **updates}, "assumption_synthesizer"))
            return updates
        except Exception as exc:
            errors.append(f"assumption_synthesizer: {exc}")
            return {
                "errors": errors,
                "assumption_probe_completed": True,
                "assumption_pending_evidence": [],
            }

    return assumption_synthesizer


def create_assumption_compliance_check(deps: EquityResearchDeps):
    def assumption_compliance_check(state: dict[str, Any]) -> dict[str, Any]:
        pending = list(
            state.get("assumption_pending_evidence")
            or state.get("pending_evidence", [])
        )
        assumptions = state.get("consensus_assumptions") or {}
        flags = list(state.get("compliance_flags", []))
        flags.extend(
            check_assumption_evidence_compliance(
                pending,
                assumptions,
                config=deps.config,
            )
        )
        updates = {"compliance_flags": flags}
        updates.update(deps.trace({**state, **updates}, "assumption_compliance_check"))
        return updates

    return assumption_compliance_check


def _report_max_chars(deps: EquityResearchDeps) -> int:
    return int(
        deps.config.get("equity_research", {}).get("consensus_report_max_chars", 6000)
    )


def create_consensus_synthesizer(deps: EquityResearchDeps):
    def consensus_synthesizer(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            raw_view = state.get("consensus_view") or {}
            if raw_view:
                view = StructuredConsensusView.model_validate(raw_view)
            else:
                view = empty_structured_consensus_view(ticker)

            pending = state.get("pending_evidence", [])
            if not pending:
                return {"consensus_view": view.model_dump(), "pending_evidence": []}

            view_text = compact_if_needed(
                deps,
                format_consensus_view(view),
                purpose="consensus view",
            )
            evidence_text = build_search_memory_for_prompt(
                deps,
                pending,
                max_chars=None,
            )
            if not evidence_text or evidence_text == "- No prior searches recorded.":
                evidence_text = format_search_memory(pending)

            prompt = (
                f"Update the structured consensus view for {ticker} using search evidence.\n"
                f"Current view:\n{view_text}\n\n"
                f"New search evidence (this round only):\n{evidence_text}\n\n"
                "Merge incrementally — do not erase existing content.\n"
                "If there is any conflict between existing content and new evidence, "
                "keep both views and label the conflict with [CON].\n"
                "Attribute evidence only to its target_dimension.\n"
                "Update dimension_coverage for each dimension.\n"
                "Do not fabricate numbers without citation in sources."
            )

            def _fallback() -> ConsensusViewUpdate:
                return ConsensusViewUpdate(ticker=ticker)

            try:
                update = invoke_structured_with_retry(
                    deps.quick_llm,
                    ConsensusViewUpdate,
                    prompt,
                    agent_name="consensus_synthesizer",
                    max_attempts=_max_retries(deps),
                    fallback=_fallback,
                )
                if any(
                    getattr(update, field) is not None
                    for field in (
                        "quantitative_estimates", "kpi_focus", "pricing_assumptions",
                        "narrative_framework", "recent_delta", "dimension_coverage",
                    )
                ):
                    view = merge_view_update(view, update)
                else:
                    _apply_evidence_heuristic(view, pending)
            except StructuredOutputUnsupported:
                _apply_evidence_heuristic(view, pending)

            _preserve_citations_from_evidence(view, pending)
            search_memory = state.get("search_memory", [])
            if search_memory:
                _preserve_citations_from_memory(view, search_memory)

            updates = {
                "consensus_view": view.model_dump(),
                "pending_evidence": [],
            }
            updates.update(deps.trace({**state, **updates}, "consensus_synthesizer"))
            return updates
        except Exception as exc:
            errors.append(f"consensus_synthesizer: {exc}")
            return {"errors": errors}

    return consensus_synthesizer


def create_coverage_reflector(deps: EquityResearchDeps):
    def coverage_reflector(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        iterations = int(state.get("consensus_iterations", 0)) + 1
        try:
            raw_view = state.get("consensus_view") or {}
            if raw_view:
                view = StructuredConsensusView.model_validate(raw_view)
            else:
                view = empty_structured_consensus_view(state.get("ticker", ""))

            search_memory = state.get("search_memory", [])
            memory_summary = ""
            if search_memory:
                memory_summary = (
                    f"\nSearch history summary:\n"
                    f"{build_search_memory_for_prompt(deps, search_memory)}\n"
                )

            view_text = compact_if_needed(
                deps,
                format_consensus_view(view),
                purpose="consensus view for coverage evaluation",
            )
            prompt = (
                f"Evaluate coverage of the consensus view for {view.ticker}.\n"
                f"View:\n{view_text}\n"
                f"{memory_summary}\n"
                "Score each dimension as empty, partial, sufficient, or strong.\n"
                "Provide an overall_score between 0 and 1.\n"
                "List critical_gaps as dimension names still weak.\n"
                "List suggested_focus as dimensions to prioritize next."
            )

            def _fallback() -> CoverageEvaluation:
                report = _default_coverage_report(view)
                return CoverageEvaluation(
                    dimension_scores=report.dimension_scores,
                    overall_score=report.overall_score,
                    critical_gaps=report.critical_gaps,
                    suggested_focus=report.suggested_focus,
                )

            try:
                evaluation = invoke_structured_with_retry(
                    deps.quick_llm,
                    CoverageEvaluation,
                    prompt,
                    agent_name="consensus_coverage_reflector",
                    max_attempts=_max_retries(deps),
                    fallback=_fallback,
                )
                report = _evaluation_to_report(evaluation)
            except StructuredOutputUnsupported:
                report = _default_coverage_report(view)

            max_iter = int(state.get("max_consensus_iterations", 5))
            if report.overall_score >= 0.75 and not report.critical_gaps:
                report.routing_decision = "exit"
            elif iterations >= max_iter:
                report.routing_decision = "exit"
            else:
                report.routing_decision = "continue"

            view.coverage_score = report.overall_score
            view.dimension_coverage = report.dimension_scores

            coverage_history = list(state.get("coverage_history", []))
            coverage_history.append(report.model_dump())

            updates = {
                "coverage_report": report.model_dump(),
                "coverage_history": coverage_history,
                "consensus_view": view.model_dump(),
                "consensus_iterations": iterations,
            }
            updates.update(deps.trace({**state, **updates}, "consensus_coverage_reflector", {
                "overall_score": report.overall_score,
                "routing": report.routing_decision,
            }))
            return updates
        except Exception as exc:
            errors.append(f"coverage_reflector: {exc}")
            return {
                "errors": errors,
                "consensus_iterations": iterations,
                "coverage_report": {"routing_decision": "exit"},
            }

    return coverage_reflector


def create_finalizer(deps: EquityResearchDeps):
    def finalizer(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            raw_view = state.get("consensus_view") or {}
            if raw_view:
                view = StructuredConsensusView.model_validate(raw_view)
            else:
                view = empty_structured_consensus_view(ticker)

            assumptions = state.get("consensus_assumptions") or {}
            coverage = state.get("coverage_report") or {}
            search_memory = state.get("search_memory", [])
            skill_ctx = state.get("active_skill_context", {})
            compliance_flags = state.get("compliance_flags", [])

            view_text = compact_if_needed(
                deps,
                format_consensus_view(view),
                purpose="consensus final report",
            )
            memory_text = ""
            if search_memory:
                memory_text = build_search_memory_for_prompt(deps, search_memory)

            compliance_text = ""
            if compliance_flags:
                compliance_text = (
                    "\nCompliance flags:\n"
                    + "\n".join(
                        f"- [{f.get('type', 'flag')}] {f.get('message', '')}"
                        for f in compliance_flags[:10]
                    )
                )

            prompt = (
                f"Write a moderate-length market consensus report for {ticker} "
                f"(target 800-1500 words, max {_report_max_chars(deps)} characters).\n\n"
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

            report = ""
            try:
                response = deps.quick_llm.invoke(prompt)
                report = response.content if hasattr(response, "content") else str(response)
                report = str(report).strip()[:_report_max_chars(deps)]
            except Exception:
                report = view.to_legacy_summary()
                if assumptions:
                    report += "\n\n## Key Assumptions Behind Consensus\n"
                    report += str(assumptions)[:2000]
                if compliance_flags:
                    report += "\n\n## Compliance Flags\n"
                    report += compliance_text

            updates: dict[str, Any] = {
                "consensus_report": report,
            }
            updates.update(deps.trace({**state, **updates}, "consensus_finalizer", {
                "iterations": state.get("consensus_iterations", 0),
                "evidence_count": len(state.get("evidence_buffer", [])),
                "report_chars": len(report),
            }))
            return updates
        except Exception as exc:
            errors.append(f"finalizer: {exc}")
            return {"errors": errors, "consensus_report": ""}

    return finalizer


def _human_review_config(deps: EquityResearchDeps) -> dict[str, Any]:
    er = deps.config.get("equity_research", {})
    defaults = {"enabled": False, "interrupt": False}
    return {**defaults, **(er.get("consensus_human_review") or {})}


def create_human_review(deps: EquityResearchDeps):
    def human_review(state: dict[str, Any]) -> dict[str, Any]:
        config = _human_review_config(deps)
        followup = str(state.get("human_followup_query") or "").strip()
        history = list(state.get("human_followup_history", []))
        coverage = dict(state.get("coverage_report") or {})

        payload = {
            "consensus_report_excerpt": str(state.get("consensus_report", ""))[:1500],
            "coverage_gaps": coverage.get("critical_gaps", []),
            "overall_score": coverage.get("overall_score", 0.0),
            "awaiting_followup": bool(config.get("enabled")) and not followup,
        }

        updates: dict[str, Any] = {
            "human_review_payload": payload,
        }

        if followup:
            history.append(followup)
            coverage["routing_decision"] = "continue"
            updates.update({
                "human_followup_history": history,
                "human_followup_query": "",
                "_pending_human_followup": True,
                "coverage_report": coverage,
                "assumption_probe_completed": False,
            })
        else:
            updates["_pending_human_followup"] = False

        updates.update(deps.trace({**state, **updates}, "consensus_human_review", {
            "has_followup": bool(followup),
            "enabled": config.get("enabled", False),
        }))
        return updates

    return human_review
