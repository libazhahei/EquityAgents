"""Tests for section question tree planner."""

from __future__ import annotations

from unittest.mock import MagicMock

from tradingagents.equity_research.agents.dynamic_planning import create_dynamic_planning
from tradingagents.equity_research.agents.section_planner.nodes import grounding_router
from tradingagents.equity_research.agents.section_planner.state import (
    build_section_planner_request,
    empty_section_planner_state,
)
from tradingagents.equity_research.agents.section_planner.subgraph import SectionPlannerSubgraph
from tradingagents.equity_research.tasks.section_planner.schemas import (
    BackgroundExtraction,
    ResearchQuestionNode,
    SectionPlannerLLMOutput,
    SectionPlannerRequest,
)
from tradingagents.equity_research.tasks.section_planner.validate import (
    finalize_plan_from_llm_output,
    normalize_plan_dict,
    validate_and_repair,
)
from tradingagents.equity_research.templates.report_template import (
    build_grounding_queries,
    get_section_intent_hint,
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


def _sample_llm_output() -> SectionPlannerLLMOutput:
    return SectionPlannerLLMOutput(
        planning_thesis="Test industry positioning thesis",
        root_question="Can NVDA sustain AI infrastructure leadership?",
        nodes=[
            ResearchQuestionNode(
                id="q0",
                parent_id=None,
                level=0,
                question="Can NVDA sustain AI infrastructure leadership?",
                rationale="Root",
                priority=1,
            ),
            ResearchQuestionNode(
                id="q1",
                parent_id="q0",
                level=1,
                question="What is AI infrastructure TAM growth?",
                rationale="TAM",
                priority=2,
                expected_output="tam_estimate",
            ),
            ResearchQuestionNode(
                id="q2",
                parent_id="q0",
                level=1,
                question="How is market share evolving?",
                rationale="Share",
                priority=3,
                expected_output="market_share_analysis",
            ),
            ResearchQuestionNode(
                id="q3",
                parent_id="q0",
                level=1,
                question="Who are the key competitors?",
                rationale="Competition",
                priority=4,
                expected_output="competitor_comparison_table",
            ),
        ],
        coverage_map={
            "tam_estimate": ["q1"],
            "industry_growth_rate": ["q1"],
            "value_chain_analysis": ["q1"],
            "market_share_analysis": ["q2"],
            "competitor_comparison_table": ["q3"],
            "competitive_position_assessment": ["q3"],
            "regulatory_or_policy_factors": ["q0"],
        },
        execution_order=["q1", "q2", "q3", "q0"],
    )


def _mock_deps(*, llm_output: SectionPlannerLLMOutput | None = None):
    from tradingagents.equity_research.runtime.utils import structured_invoke

    structured_invoke._RUNNABLE_CACHE.clear()
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.trace.return_value = {}

    output = llm_output or _sample_llm_output()
    _bind_structured_mock(
        deps.quick_llm,
        BackgroundExtraction,
        BackgroundExtraction(
            market_implied_assumptions=["hyperscaler capex remains strong"],
            controversies=["Blackwell ramp timing"],
            evidence_gaps=["China export impact"],
        ),
    )
    _bind_structured_mock(deps.quick_llm, SectionPlannerLLMOutput, output)
    return deps


def _sample_request() -> SectionPlannerRequest:
    return SectionPlannerRequest(
        ticker="NVDA",
        section_id="4_industry_and_competition",
        section_title="Industry Analysis & Competitive Landscape",
        required_outputs=[
            "tam_estimate",
            "industry_growth_rate",
            "value_chain_analysis",
            "market_share_analysis",
            "competitor_comparison_table",
            "competitive_position_assessment",
            "regulatory_or_policy_factors",
        ],
        background_reports={"consensus_report": "NVDA dominates AI accelerators."},
        section_intent_hint=get_section_intent_hint("4_industry_and_competition"),
    )


def test_template_has_intent_hint_and_grounding_queries():
    hint = get_section_intent_hint("4_industry_and_competition")
    assert "TAM" in hint
    queries = build_grounding_queries("4_industry_and_competition", "NVDA")
    assert len(queries) <= 5
    assert any("NVDA" in q for q in queries)


def test_normalize_plan_fills_missing_coverage():
    req = _sample_request()
    data = {"nodes": [], "root_question": "Root?"}
    normalized = normalize_plan_dict(data, req)
    repaired = validate_and_repair(normalized, req)
    plan = finalize_plan_from_llm_output(repaired, req)
    for output in req.required_outputs:
        assert output in plan.coverage_map
        assert plan.coverage_map[output]


def test_validate_flags_few_sub_questions():
    req = _sample_request()
    data = normalize_plan_dict({
        "root_question": "Root?",
        "nodes": [
            {"id": "q0", "parent_id": None, "level": 0, "question": "Root?", "rationale": "r", "priority": 1},
            {"id": "q1", "parent_id": "q0", "level": 1, "question": "Sub?", "rationale": "r", "priority": 2},
        ],
    }, req)
    data = validate_and_repair(data, req)
    assert "planner_generated_fewer_than_3_sub_questions" in data["data_quality_flags"]


def test_grounding_router_respects_enable_flag():
    enabled = {"enable_grounding": True, "allowed_tools": ["web_search"]}
    disabled = {"enable_grounding": False, "allowed_tools": ["web_search"]}
    assert grounding_router(enabled) == "grounding_dispatch"
    assert grounding_router(disabled) == "question_tree_generator"


def test_section_planner_subgraph_mock():
    deps = _mock_deps()
    req = _sample_request()
    compiled = SectionPlannerSubgraph(deps).compile()
    result = compiled.invoke(empty_section_planner_state(req))

    plan = result["plan"]
    assert plan["section_id"] == "4_industry_and_competition"
    assert plan["root_question"]
    assert len(plan["nodes"]) >= 1
    assert result["exploration_graph"]["nodes"]
    snapshot = next(iter(result["exploration_graph"]["nodes"].values()))["structured_view_snapshot"]
    assert snapshot["type"] == "section_research_plan"


def test_dynamic_planning_plans_multiple_sections():
    deps = _mock_deps()
    planner = create_dynamic_planning(deps)
    state = {
        "ticker": "NVDA",
        "consensus_report": "Consensus text",
        "assumption_report": "Assumption text",
        "research_iterations": 0,
        "max_research_iterations": 5,
        "api_calls": 0,
        "research_traces": [],
        "errors": [],
    }
    result = planner(state)
    assert "section_plans" in result
    assert len(result["section_plans"]) >= 5
    assert "4_industry_and_competition" in result["section_plans"]
    assert result["research_plan"].get("core_questions")
    assert result["research_strategy"].get("priority_questions")


def test_build_section_planner_request_from_state():
    state = {"ticker": "NVDA", "sector": "Technology"}
    req = build_section_planner_request(
        state,
        "3_business_model",
        {"consensus_report": "report"},
        enable_grounding=True,
    )
    assert req.ticker == "NVDA"
    assert req.section_id == "3_business_model"
    assert req.enable_grounding is True
    assert "web_search" in req.allowed_tools
