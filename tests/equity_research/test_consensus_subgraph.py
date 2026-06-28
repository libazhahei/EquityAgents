"""Tests for consensus subgraph."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage
from pydantic import ValidationError

from tradingagents.equity_research.agents.consensus.compliance import (
    append_compliance_suffix,
    filter_compliant_citations,
)
from tradingagents.equity_research.agents.consensus.merge_utils import merge_view_update
from tradingagents.equity_research.agents.consensus.nodes import (
    create_assumption_batch_executor,
    create_assumption_query_planner,
    create_assumption_synthesizer,
    create_consensus_planner,
    create_consensus_synthesizer,
    create_coverage_reflector,
    create_finalizer,
    create_human_review,
    create_query_batch_executor,
    create_query_executor,
    create_query_planner,
    create_skill_selector,
)
from tradingagents.equity_research.agents.consensus.routers import (
    assumption_probe_gate_router,
    coverage_reflector_router,
    gap_query_planner_router,
    human_review_router,
    skill_selector_router,
)
from tradingagents.equity_research.agents.consensus.search_memory import format_search_memory
from tradingagents.equity_research.agents.consensus.structured_invoke import invoke_structured_with_retry
from tradingagents.equity_research.agents.consensus.subgraph import ConsensusSubgraph, create_run_consensus_subgraph
from tradingagents.equity_research.agents.consensus_agents import create_gap_finder
from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    ConsensusAssumptions,
    ConsensusViewUpdate,
    CoverageEvaluation,
    CoverageStatus,
    ExpectationGapBatch,
    ExpectationGapInput,
    NarrativeFramework,
    QueryItem,
    QueryPlan,
    SearchMode,
    SkillSelectionResult,
    StructuredConsensusView,
    empty_structured_consensus_view,
    get_consensus_summary,
)


def _bind_structured_mock(llm: MagicMock, schema: type, return_value):
    if not isinstance(getattr(llm, "_structured_returns", None), dict):
        llm._structured_returns = {}

    def _factory(requested_schema, **_kwargs):
        structured = MagicMock()
        value = llm._structured_returns.get(requested_schema)
        if value is None:
            value = return_value
        structured.invoke.return_value = value
        structured.with_retry.return_value = structured
        return structured

    llm._structured_returns[schema] = return_value
    llm.with_structured_output.side_effect = _factory
    return llm


def _mock_skill_bind_tools(deps: MagicMock, skill_names: list[str] | None = None) -> None:
    names = skill_names or ["broker_consensus_mining"]
    tool_call_msg = AIMessage(
        content="",
        tool_calls=[{
            "name": "load_research_skills",
            "args": {"skill_names": names},
            "id": "call_test_1",
        }],
    )
    bound = MagicMock()
    bound.invoke.return_value = tool_call_msg
    deps.quick_llm.bind_tools.return_value = bound


def _mock_deps(
    *,
    skill_names: list[str] | None = None,
    skill_result: SkillSelectionResult | None = None,
    planner_result: QueryPlan | None = None,
    synthesizer_result: ConsensusViewUpdate | None = None,
    reflector_result: CoverageEvaluation | None = None,
    assumption_result: ConsensusAssumptions | None = None,
    gap_result: ExpectationGapBatch | None = None,
    perplexity_answer: str = "consensus data",
    perplexity_citations: list[str] | None = None,
):
    from tradingagents.equity_research.agents.consensus import structured_invoke

    structured_invoke._RUNNABLE_CACHE.clear()

    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.trace.return_value = {}
    deps.perplexity.api_key = "test-key"
    deps.perplexity.search.return_value = {
        "answer": perplexity_answer,
        "citations": perplexity_citations or ["https://example.com/consensus"],
    }
    deps.documents.register.return_value = {"doc_id": "doc_1"}

    compact_resp = MagicMock()
    compact_resp.content = "compacted text"
    deps.quick_llm.invoke.return_value = compact_resp

    _mock_skill_bind_tools(deps, skill_names)

    if skill_result is not None:
        _bind_structured_mock(deps.quick_llm, SkillSelectionResult, skill_result)
    if planner_result is not None:
        _bind_structured_mock(deps.deep_llm, QueryPlan, planner_result)
    if synthesizer_result is not None:
        _bind_structured_mock(deps.quick_llm, ConsensusViewUpdate, synthesizer_result)
    if reflector_result is not None:
        _bind_structured_mock(deps.quick_llm, CoverageEvaluation, reflector_result)
    if assumption_result is not None:
        _bind_structured_mock(deps.quick_llm, ConsensusAssumptions, assumption_result)
    if gap_result is not None:
        _bind_structured_mock(deps.deep_llm, ExpectationGapBatch, gap_result)

    if assumption_result is None and (synthesizer_result is not None or reflector_result is not None):
        _bind_structured_mock(
            deps.quick_llm,
            ConsensusAssumptions,
            ConsensusAssumptions(
                business_model="Subscription and services revenue",
                market_sentiment="bullish",
                sources=["https://example.com/consensus"],
            ),
        )

    return deps


def test_structured_consensus_view_legacy_summary():
    view = empty_structured_consensus_view("NVDA")
    view.narrative_framework.bull_case = "AI leadership drives growth"
    view.narrative_framework.bear_case = "Competition intensifies"
    summary = view.to_legacy_summary()
    assert "NVDA" in summary or "AI leadership" in summary


def test_skill_selector_uses_llm_chosen_skills():
    deps = _mock_deps(skill_names=["broker_consensus_mining"])
    node = create_skill_selector(deps)
    result = node({"ticker": "NVDA", "sector": "Tech", "errors": []})
    assert result["active_skills"] == ["broker_consensus_mining"]
    assert result["active_skill_context"]["prompt_template"]
    assert result["skill_catalog"]
    assert "broker_consensus_mining" in result["loaded_skills"]
    assert "perplexity_search" not in str(result["skill_catalog"])
    deps.quick_llm.bind_tools.assert_called()


def test_skill_selector_tool_node_flow():
    deps = _mock_deps(skill_names=["broker_consensus_mining"])
    agent = create_skill_selector(deps)
    state = {"ticker": "NVDA", "sector": "Tech", "errors": []}
    result = agent(state)
    assert result["active_skills"] == ["broker_consensus_mining"]
    assert result.get("messages") == []


def test_skill_selector_router_routes_tool_calls():
    msg = AIMessage(
        content="",
        tool_calls=[{"name": "load_research_skills", "args": {}, "id": "1"}],
    )
    assert skill_selector_router({"messages": [msg]}) == "tools"
    assert skill_selector_router({"messages": [AIMessage(content="done")]}) == "apply"


def test_skill_selector_fallback_on_bad_llm_response():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.trace.return_value = {}
    deps.quick_llm.bind_tools.side_effect = RuntimeError("bind failed")

    node = create_skill_selector(deps)
    result = node({"ticker": "NVDA", "errors": []})
    assert result["active_skills"]
    assert result["active_skills"][0] == "broker_consensus_mining"


def test_query_executor_does_not_call_structured_llm():
    deps = _mock_deps()
    state = {
        "ticker": "NVDA",
        "query_queue": [{
            "query": "NVDA analyst consensus revenue estimates",
            "target_dimension": "quantitative_estimates",
            "mode": "targeted",
            "priority": 5,
        }],
        "executed_queries": [],
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": [],
        "documents": [],
        "api_calls": 0,
        "errors": [],
        "consensus_iterations": 0,
    }
    result = create_query_executor(deps)(state)
    deps.deep_llm.with_structured_output.assert_not_called()
    deps.perplexity.search.assert_called_once()
    assert len(result["evidence_buffer"]) == 1
    assert len(result["pending_evidence"]) == 1
    assert result["evidence_buffer"][0]["target_dimension"] == "quantitative_estimates"


def test_search_memory_appended_after_query_executor():
    citations = [
        "https://example.com/a",
        "https://example.com/b",
        "https://example.com/c",
    ]
    deps = _mock_deps(perplexity_citations=citations)
    state = {
        "ticker": "NVDA",
        "query_queue": [{
            "query": "NVDA revenue estimates",
            "target_dimension": "quantitative_estimates",
            "mode": "targeted",
            "priority": 5,
        }],
        "executed_queries": [],
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": [],
        "documents": [],
        "api_calls": 0,
        "errors": [],
        "consensus_iterations": 1,
    }
    result = create_query_executor(deps)(state)
    assert len(result["search_memory"]) == 1
    assert result["search_memory"][0]["citations"] == citations
    assert result["executed_queries"] == ["NVDA revenue estimates"]


def test_coverage_reflector_router_exit_on_score():
    state = {"coverage_report": {"routing_decision": "exit"}}
    assert coverage_reflector_router(state) == "exit"


def test_coverage_reflector_router_continue_with_empty_queue():
    state = {"coverage_report": {"routing_decision": "continue"}, "query_queue": []}
    assert coverage_reflector_router(state) == "plan_more"


def test_coverage_reflector_router_continue_with_remaining_queue():
    state = {
        "coverage_report": {"routing_decision": "continue"},
        "query_queue": [{"query": "next", "target_dimension": "kpi_focus"}],
    }
    assert coverage_reflector_router(state) == "run_existing_queue"


def test_gap_query_planner_router_exit_on_empty_queue():
    assert gap_query_planner_router({"query_queue": []}) == "exit"


def test_gap_query_planner_router_run_when_queue_populated():
    assert gap_query_planner_router({"query_queue": [{"query": "x"}]}) == "run"


def test_coverage_reflector_exits_at_max_iterations():
    dim_scores = {dim: CoverageStatus.PARTIAL for dim in CONSENSUS_DIMENSIONS}
    deps = _mock_deps(
        reflector_result=CoverageEvaluation(
            dimension_scores=dim_scores,
            overall_score=0.5,
            critical_gaps=["quantitative_estimates"],
            suggested_focus=["quantitative_estimates"],
        ),
    )
    state = {
        "ticker": "NVDA",
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
        "consensus_iterations": 4,
        "max_consensus_iterations": 5,
        "search_memory": [],
        "errors": [],
    }
    result = create_coverage_reflector(deps)(state)
    assert result["coverage_report"]["routing_decision"] == "exit"
    assert result["consensus_iterations"] == 5


def test_consensus_subgraph_wrapper_writes_structured_view():
    planner = QueryPlan(queries=[
        QueryItem(
            query="NVDA bull bear case",
            target_dimension="narrative_framework",
            mode=SearchMode.EXPLORATORY,
            priority=3,
        ),
    ])
    reflector = CoverageEvaluation(
        dimension_scores={dim: CoverageStatus.SUFFICIENT for dim in CONSENSUS_DIMENSIONS},
        overall_score=0.9,
        critical_gaps=[],
        suggested_focus=[],
    )
    synthesizer = ConsensusViewUpdate(
        ticker="NVDA",
        narrative_framework=NarrativeFramework(
            bull_case="AI growth",
            bear_case="competition",
            sources=["https://example.com"],
        ),
    )
    deps = _mock_deps(
        planner_result=planner,
        synthesizer_result=synthesizer,
        reflector_result=reflector,
    )

    run = create_run_consensus_subgraph(deps)
    parent = {"ticker": "NVDA", "sector": "Technology", "documents": [], "api_calls": 0, "errors": []}
    result = run(parent)

    assert isinstance(result["consensus_view"], dict)
    assert result["consensus_view"].get("ticker") == "NVDA" or result["consensus_view"]
    assert result["consensus_iterations"] >= 1
    assert "consensus_search_memory" in result
    assert "consensus_report" in result
    assert "consensus_assumptions" in result


def test_gap_finder_includes_source_dimension():
    deps = _mock_deps(
        gap_result=ExpectationGapBatch(gaps=[
            ExpectationGapInput(
                description="Market underestimates cloud growth",
                alpha_source="variant",
                materiality=0.8,
                verifiability=0.6,
                related_metrics=["revenue"],
                source_dimension="quantitative_estimates",
                consensus_assumption="10% growth",
                variant_view="15% growth",
            ),
        ]),
    )
    view = empty_structured_consensus_view("NVDA")
    state = {
        "ticker": "NVDA",
        "consensus_view": view.model_dump(),
        "instrument_context": "AI chip leader",
    }
    result = create_gap_finder(deps)(state)
    gaps = result["expectation_gaps"]
    assert len(gaps) >= 1
    assert gaps[0].get("source_dimension") == "quantitative_estimates"


def test_get_consensus_summary_handles_structured_and_legacy():
    structured = empty_structured_consensus_view("AAPL")
    structured.narrative_framework.bull_case = "Services growth"
    assert "Services growth" in get_consensus_summary({"consensus_view": structured.model_dump()})
    assert get_consensus_summary({"consensus_view": [{"summary": "legacy text"}]}) == "legacy text"


def test_consensus_subgraph_compiles():
    deps = _mock_deps()
    graph = ConsensusSubgraph(deps).compile()
    assert graph is not None


def test_subgraph_graph_includes_human_review():
    deps = _mock_deps()
    graph = ConsensusSubgraph(deps).build()
    node_names = set(graph.nodes.keys())
    assert "human_review" in node_names
    assert "assumption_query_planner" in node_names
    assert "skill_selector_agent" in node_names


def test_assumption_probe_gate_router():
    assert assumption_probe_gate_router({"assumption_probe_completed": False}) == "probe"
    assert assumption_probe_gate_router({"assumption_probe_completed": True}) == "done"


def test_assumption_probe_runs_once_on_exit():
    deps = _mock_deps(
        assumption_result=ConsensusAssumptions(
            business_model="Chip sales",
            market_sentiment="bullish",
            sources=["https://example.com/consensus"],
        ),
    )
    state = {
        "ticker": "NVDA",
        "query_queue": [{
            "query": append_compliance_suffix("NVDA business model revenue drivers"),
            "target_dimension": "narrative_framework",
            "mode": "exploratory",
            "priority": 5,
        }],
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": [],
        "documents": [],
        "api_calls": 0,
        "errors": [],
        "consensus_iterations": 1,
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
    }
    create_assumption_batch_executor(deps)(state)
    synth_state = {
        **state,
        "assumption_pending_evidence": [{
            "answer": "AI chip demand",
            "citations": ["https://example.com/consensus"],
            "target_dimension": "narrative_framework",
            "query_used": "NVDA business model",
        }],
    }
    result = create_assumption_synthesizer(deps)(synth_state)
    assert result["assumption_probe_completed"] is True
    assert result["consensus_assumptions"]["business_model"]


def test_assumption_planner_covers_theme_checklist():
    from tradingagents.equity_research.agents.consensus import structured_invoke

    structured_invoke._RUNNABLE_CACHE.clear()
    captured: dict[str, str] = {}
    deps = _mock_deps(planner_result=QueryPlan(queries=[]))

    def _capture_plan(requested_schema, **_kwargs):
        structured = MagicMock()
        structured.with_retry.return_value = structured
        structured.invoke.side_effect = lambda prompt: (
            captured.__setitem__("prompt", prompt) or QueryPlan(queries=[])
        )
        return structured

    deps.deep_llm.with_structured_output.side_effect = _capture_plan
    structured_invoke._RUNNABLE_CACHE.clear()
    create_assumption_query_planner(deps)({
        "ticker": "NVDA",
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
        "coverage_report": {},
        "search_memory": [],
        "errors": [],
    })
    assert "How does this company make money?" in captured["prompt"]
    assert "publicly available" in captured["prompt"].lower()


def test_assumption_compliance_flags_missing_citation():
    kept, flags = filter_compliant_citations([""])
    assert kept == []
    assert any(f["type"] == "missing_citation" for f in flags)
    kept2, flags2 = filter_compliant_citations(["not-a-url"])
    assert kept2 == []
    assert any(f["type"] == "non_public_source" for f in flags2)


def test_finalizer_writes_consensus_report():
    deps = _mock_deps()
    report_resp = MagicMock()
    report_resp.content = "## Key Assumptions Behind Consensus\nBullish AI demand."
    deps.quick_llm.invoke.return_value = report_resp
    state = {
        "ticker": "NVDA",
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
        "consensus_assumptions": {"business_model": "Chips"},
        "coverage_report": {},
        "search_memory": [],
        "active_skill_context": {},
        "compliance_flags": [],
        "evidence_buffer": [],
        "consensus_iterations": 1,
        "errors": [],
    }
    result = create_finalizer(deps)(state)
    assert "Key Assumptions Behind Consensus" in result["consensus_report"]


def test_human_review_pass_through():
    deps = _mock_deps()
    state = {
        "consensus_report": "report text",
        "coverage_report": {"critical_gaps": [], "overall_score": 0.9},
        "human_followup_query": "",
        "human_followup_history": [],
        "errors": [],
    }
    result = create_human_review(deps)(state)
    assert human_review_router({**state, **result}) == "done"


def test_human_review_routes_to_gap_planner():
    deps = _mock_deps()
    state = {
        "consensus_report": "report text",
        "coverage_report": {"critical_gaps": ["kpi_focus"], "overall_score": 0.5},
        "human_followup_query": "Dig deeper into cloud KPI trends",
        "human_followup_history": [],
        "errors": [],
    }
    result = create_human_review(deps)(state)
    merged = {**state, **result}
    assert human_review_router(merged) == "replan"
    assert "cloud KPI" in merged["human_followup_history"][-1]


def test_synthesizer_preserves_all_perplexity_citations():
    citations = [
        "https://example.com/one",
        "https://example.com/two",
        "https://example.com/three",
    ]
    deps = _mock_deps(
        synthesizer_result=ConsensusViewUpdate(ticker="NVDA"),
    )
    view = empty_structured_consensus_view("NVDA")
    state = {
        "ticker": "NVDA",
        "consensus_view": view.model_dump(),
        "pending_evidence": [{
            "answer": "consensus data",
            "citations": citations,
            "target_dimension": "quantitative_estimates",
            "query_used": "NVDA estimates",
            "doc_ids": ["doc_1"],
        }],
        "search_memory": [{
            "query": "NVDA estimates",
            "target_dimension": "quantitative_estimates",
            "mode": "targeted",
            "iteration": 0,
            "answer": "consensus data",
            "answer_summary": "consensus data",
            "citations": citations,
            "doc_ids": ["doc_1"],
        }],
        "errors": [],
    }
    result = create_consensus_synthesizer(deps)(state)
    sources = result["consensus_view"]["quantitative_estimates"]["sources"]
    for url in citations:
        assert url in sources
    assert result["pending_evidence"] == []


def test_query_planner_receives_search_memory_in_prompt():
    from tradingagents.equity_research.agents.consensus import structured_invoke

    structured_invoke._RUNNABLE_CACHE.clear()
    captured: dict[str, str] = {}
    deps = _mock_deps(planner_result=QueryPlan(queries=[]))

    def _capture_plan(requested_schema, **_kwargs):
        structured = MagicMock()
        structured.with_retry.return_value = structured
        structured.invoke.side_effect = lambda prompt: (
            captured.__setitem__("prompt", prompt) or QueryPlan(queries=[])
        )
        return structured

    deps.deep_llm.with_structured_output.side_effect = _capture_plan
    structured_invoke._RUNNABLE_CACHE.clear()

    state = {
        "ticker": "NVDA",
        "coverage_report": {
            "critical_gaps": ["quantitative_estimates"],
            "suggested_focus": ["quantitative_estimates"],
            "dimension_scores": {"quantitative_estimates": "partial"},
            "overall_score": 0.4,
            "routing_decision": "continue",
        },
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
        "consensus_iterations": 2,
        "max_consensus_iterations": 5,
        "active_skill_context": {},
        "search_memory": [{
            "iteration": 1,
            "target_dimension": "quantitative_estimates",
            "mode": "targeted",
            "query": "NVDA revenue consensus",
            "answer_summary": "Revenue growth 20%",
            "citations": ["https://example.com/prior"],
        }],
        "executed_queries": [],
        "query_queue": [],
        "errors": [],
    }
    create_query_planner(deps)(state)
    assert "NVDA revenue consensus" in captured["prompt"]
    assert "https://example.com/prior" in captured["prompt"]
    assert "quantitative_estimates: partial" in captured["prompt"]
    assert "Overall score: 0.4" in captured["prompt"]
    assert "Round: 2 / 5" in captured["prompt"]


def test_synthesizer_uses_pending_evidence_only():
    from tradingagents.equity_research.agents.consensus import structured_invoke

    structured_invoke._RUNNABLE_CACHE.clear()
    captured: dict[str, str] = {}
    deps = _mock_deps(
        synthesizer_result=ConsensusViewUpdate(ticker="NVDA"),
    )

    def _capture_synth(requested_schema, **_kwargs):
        structured = MagicMock()
        structured.with_retry.return_value = structured
        structured.invoke.side_effect = lambda prompt: (
            captured.__setitem__("prompt", prompt) or ConsensusViewUpdate(ticker="NVDA")
        )
        return structured

    deps.quick_llm.with_structured_output.side_effect = _capture_synth
    structured_invoke._RUNNABLE_CACHE.clear()

    records = []
    for i in range(5):
        records.append({
            "iteration": i,
            "target_dimension": "narrative_framework",
            "mode": "exploratory",
            "query": f"query {i}",
            "answer_summary": f"finding {i}",
            "citations": [f"https://example.com/{i}"],
        })

    state = {
        "ticker": "NVDA",
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
        "pending_evidence": records,
        "errors": [],
    }
    create_consensus_synthesizer(deps)(state)
    for i in range(5):
        assert f"https://example.com/{i}" in captured["prompt"]
    assert "this round only" in captured["prompt"].lower()


def test_structured_invoke_retries_on_validation_error():
    from tradingagents.equity_research.agents.consensus import structured_invoke

    structured_invoke._RUNNABLE_CACHE.clear()

    llm = MagicMock()
    calls = {"count": 0}

    inner = MagicMock()

    def _invoke(_prompt):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValidationError.from_exception_data("SkillSelectionResult", [])
        return SkillSelectionResult(load_skills=["broker_consensus_mining"], reason="ok")

    inner.invoke.side_effect = _invoke

    retry_runnable = MagicMock()

    def _retry_invoke(prompt):
        last_exc = None
        for _ in range(3):
            try:
                return inner.invoke(prompt)
            except ValidationError as exc:
                last_exc = exc
        raise last_exc

    retry_runnable.invoke.side_effect = _retry_invoke

    structured = MagicMock()
    structured.with_retry.return_value = retry_runnable
    llm.with_structured_output.return_value = structured

    result = invoke_structured_with_retry(
        llm,
        SkillSelectionResult,
        "pick skills",
        agent_name="test",
        max_attempts=3,
    )
    assert result.load_skills == ["broker_consensus_mining"]
    assert calls["count"] == 2


def test_gap_planner_empty_fallback_does_not_add_default_queries():
    deps = _mock_deps(planner_result=QueryPlan(queries=[]))
    state = {
        "ticker": "NVDA",
        "coverage_report": {
            "critical_gaps": ["kpi_focus"],
            "suggested_focus": ["kpi_focus"],
            "dimension_scores": {"kpi_focus": "empty"},
            "overall_score": 0.2,
            "routing_decision": "continue",
        },
        "consensus_view": empty_structured_consensus_view("NVDA").model_dump(),
        "consensus_iterations": 1,
        "max_consensus_iterations": 5,
        "active_skill_context": {},
        "search_memory": [],
        "executed_queries": [],
        "query_queue": [],
        "errors": [],
    }
    result = create_query_planner(deps)(state)
    assert result["query_queue"] == []


def test_query_batch_executor_runs_up_to_batch_size():
    deps = _mock_deps()
    queue = []
    for i in range(5):
        queue.append({
            "query": f"NVDA query {i}",
            "target_dimension": "quantitative_estimates",
            "mode": "targeted",
            "priority": i,
        })
    state = {
        "ticker": "NVDA",
        "query_queue": queue,
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": [],
        "documents": [],
        "api_calls": 0,
        "errors": [],
        "consensus_iterations": 0,
    }
    result = create_query_batch_executor(deps, batch_size=5)(state)
    assert deps.perplexity.search.call_count == 5
    assert result["query_queue"] == []
    assert len(result["pending_evidence"]) == 5
    assert len(result["evidence_buffer"]) == 5


def test_documents_dedup_on_batch_executor():
    deps = _mock_deps()
    state = {
        "ticker": "NVDA",
        "query_queue": [{
            "query": "NVDA estimates",
            "target_dimension": "quantitative_estimates",
            "mode": "targeted",
            "priority": 5,
        }],
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": [],
        "documents": [{"doc_id": "doc_1"}],
        "api_calls": 0,
        "errors": [],
        "consensus_iterations": 0,
    }
    result = create_query_executor(deps)(state)
    doc_ids = [d["doc_id"] for d in result["documents"]]
    assert doc_ids.count("doc_1") == 1


def test_merge_view_update_appends_sources():
    from tradingagents.equity_research.state.consensus_schemas import QuantitativeEstimates

    view = empty_structured_consensus_view("NVDA")
    view.quantitative_estimates.sources = ["https://example.com/a"]
    update = ConsensusViewUpdate(
        ticker="NVDA",
        quantitative_estimates=QuantitativeEstimates(sources=["https://example.com/b"]),
    )
    merged = merge_view_update(view, update)
    assert merged.quantitative_estimates.sources == [
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_format_search_memory_includes_all_citations():
    records = [
        {
            "iteration": 0,
            "target_dimension": "kpi_focus",
            "mode": "exploratory",
            "query": "NVDA KPIs",
            "answer_summary": "Data center revenue key",
            "citations": ["https://a.com", "https://b.com"],
        },
    ]
    text = format_search_memory(records)
    assert "https://a.com" in text
    assert "https://b.com" in text
