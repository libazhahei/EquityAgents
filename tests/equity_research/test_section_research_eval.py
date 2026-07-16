"""Unit tests for section research evaluation scaffold (mocked, no network/LLM)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.section_research.evaluators.end_to_end import (
    evaluate_end_to_end,
    score_completion,
    score_schema,
)
from evaluation.section_research.evaluators.faithfulness import (
    build_evidence_pack,
    summarize_evidence_for_prompt,
)
from evaluation.section_research.evaluators.merge import deltas_exceed_threshold, merge_scores
from evaluation.section_research.evaluators.trajectory import evaluate_trajectory, score_trajectory
from evaluation.section_research.judge.rubric import (
    load_rubric,
    rubric_markdown_table,
    weighted_judge_overall,
)
from evaluation.section_research.judge.structured import build_judge_prompt
from evaluation.section_research.types import (
    ChildRunSummary,
    EvalBundle,
    FixtureMeta,
    JudgeBreakdown,
    RubricBreakdown,
)

DATASETS = Path(__file__).resolve().parents[2] / "evaluation" / "section_research" / "datasets"


@pytest.fixture
def good_bundle() -> EvalBundle:
    final_state = {
        "ticker": "NVDA",
        "section_id": "3_business_model",
        "final_report": "",
        "section_research_output": {
            "section_id": "3_business_model",
            "section_title": "Business Model",
            "final_section_text": (
                "NVIDIA monetizes AI accelerators and networking across data center and "
                "gaming segments. Hyperscalers drive the majority of growth. CUDA creates "
                "switching costs that support pricing power over multi-year cycles."
            ),
            "executive_summary": "Platform + accelerator model.",
            "answer_cards": {
                "q_segments": {
                    "question_id": "q_segments",
                    "short_answer": "Data center dominant",
                    "analysis": "Mix skewed to DC GPUs",
                    "citations": [{"url": "https://example.com/10k", "title": "10-K"}],
                    "confidence": 0.7,
                }
            },
            "citations": [{"url": "https://example.com/10k", "title": "10-K"}],
            "research_plan": {
                "plan_id": "plan_3_business_model",
                "section_id": "3_business_model",
                "tasks": [
                    {
                        "task_id": "t1",
                        "question_id": "q_segments",
                        "objective": "Segment mix",
                        "steps": [
                            {
                                "step_id": "s1",
                                "order": 1,
                                "action": "search",
                                "description": "Find segment revenue",
                            }
                        ],
                    }
                ],
                "execution_order": ["t1"],
            },
            "unresolved_gaps": ["Customer concentration detail limited"],
            "data_quality_notes": ["Stub sources"],
        },
        "coverage_report": {
            "overall_score": 0.7,
            "plan_completion": {
                "tasks_total": 1,
                "tasks_done": 1,
                "steps_total": 1,
                "steps_done": 1,
                "blocked_steps": [],
            },
            "question_scores": {"q_segments": 0.8},
            "coverage_outputs_completed": ["q_segments"],
            "critical_gaps": [],
            "data_quality_issues": [],
            "contradictions": [],
            "recommended_next_action": "exit",
            "routing_decision": "exit",
        },
        "evidence_ledger": [
            {
                "evidence_id": "e1",
                "claim": "Data center is the primary growth segment",
                "source": "10-K",
                "citation": "https://example.com/10k",
            }
        ],
        "research_traces": [],
    }
    return EvalBundle(
        ticker="NVDA",
        section_id="3_business_model",
        final_state=final_state,
        child_runs=[
            ChildRunSummary(
                name="web_search",
                run_type="tool",
                inputs={"query": "NVDA revenue segments"},
                outputs={"results": [{"title": "10-K"}]},
            ),
            ChildRunSummary(
                name="filings_search",
                run_type="tool",
                inputs={"query": "NVDA business"},
            ),
        ],
        evidence=build_evidence_pack(final_state, tool_outputs=[
            {"name": "web_search", "outputs": {"results": [{"title": "10-K"}]}},
        ]),
        fixture_meta=FixtureMeta(
            case_id="nvda_3_business_model",
            ticker="NVDA",
            section_id="3_business_model",
            reference_notes="unit test",
        ),
        source="mock",
    )


@pytest.mark.unit
def test_dataset_fixture_loads():
    path = DATASETS / "nvda_3_business_model.json"
    assert path.exists()
    raw = json.loads(path.read_text(encoding="utf-8"))
    meta = FixtureMeta.model_validate(raw)
    assert meta.ticker == "NVDA"
    assert meta.section_id == "3_business_model"
    bg = DATASETS / meta.background_json
    planner = DATASETS / meta.planner_json
    assert bg.exists()
    assert planner.exists()


@pytest.mark.unit
def test_completion_and_schema_scores(good_bundle: EvalBundle):
    c_score, c_details = score_completion(good_bundle)
    assert c_score >= 0.9
    assert c_details["has_substantial_text"] is True

    s_score, s_details = score_schema(good_bundle)
    assert s_score == 1.0
    assert "SectionResearchOutput" in s_details["ok"]

    e2e = evaluate_end_to_end(good_bundle)
    assert e2e["completion_score"] >= 0.9
    assert e2e["schema_score"] == 1.0


@pytest.mark.unit
def test_completion_fails_on_empty():
    bundle = EvalBundle(
        ticker="NVDA",
        section_id="3_business_model",
        final_state={"section_research_output": {"final_section_text": ""}},
        fixture_meta=FixtureMeta(ticker="NVDA", section_id="3_business_model"),
    )
    score, details = score_completion(bundle)
    assert score < 0.5
    assert details["has_substantial_text"] is False


@pytest.mark.unit
def test_trajectory_allows_known_tools(good_bundle: EvalBundle):
    score, details = score_trajectory(good_bundle)
    assert score >= 0.9
    assert details["unknown_tools"] == []
    assert details["tool_call_count"] == 2

    # Unknown tool penalty
    bad = good_bundle.model_copy(deep=True)
    bad.child_runs.append(
        ChildRunSummary(name="unknown_tool", run_type="tool", inputs={"query": "x"})
    )
    bad_score, bad_details = score_trajectory(bad)
    assert bad_score < score
    assert "unknown_tool" in bad_details["unknown_tools"]


@pytest.mark.unit
def test_trajectory_repeated_query_penalty(good_bundle: EvalBundle):
    bundle = good_bundle.model_copy(deep=True)
    bundle.child_runs = [
        ChildRunSummary(name="web_search", run_type="tool", inputs={"query": "same"})
        for _ in range(5)
    ]
    score, details = score_trajectory(bundle)
    assert details["repeated_queries"]
    assert score < 1.0


@pytest.mark.unit
def test_evidence_pack_and_summary(good_bundle: EvalBundle):
    pack = good_bundle.evidence
    assert pack.evidence_ledger
    assert pack.citations
    summary = summarize_evidence_for_prompt(pack)
    assert "evidence_ledger" in summary
    assert "Data center" in summary or "citations" in summary


@pytest.mark.unit
def test_rubric_table_and_judge_prompt(good_bundle: EvalBundle):
    rubric = load_rubric()
    table = rubric_markdown_table(rubric)
    assert "faithfulness" in table
    assert "| Dimension |" in table

    prompt = build_judge_prompt(good_bundle, rubric)
    assert "Rubric breakdown" in prompt or "rubric" in prompt.lower()
    assert "NVDA" in prompt
    assert "content_quality" in prompt


@pytest.mark.unit
def test_merge_scores_and_deltas(good_bundle: EvalBundle):
    rubric = load_rubric()
    judge = JudgeBreakdown(
        content_quality=0.8,
        coverage_vs_plan=0.7,
        faithfulness=0.9,
        gaps_honesty=0.75,
        overall=0.8,
    )
    good_bundle.fixture_meta.expected_scores = {
        "overall_score": 0.85,
        "faithfulness": 0.95,
    }
    report = merge_scores(
        good_bundle,
        completion_score=1.0,
        schema_score=1.0,
        trajectory_score=1.0,
        judge=judge,
        rubric=rubric,
    )
    assert report.overall_score > 0
    assert report.faithfulness_score == 0.9
    assert "overall_score" in report.deltas
    assert "faithfulness" in report.deltas

    # Force a large delta failure
    good_bundle.fixture_meta.expected_scores = {"overall_score": 0.1}
    report2 = merge_scores(
        good_bundle,
        completion_score=1.0,
        schema_score=1.0,
        trajectory_score=1.0,
        judge=judge,
        rubric=rubric,
    )
    failed = deltas_exceed_threshold(report2, rubric)
    assert "overall_score" in failed


@pytest.mark.unit
def test_weighted_judge_overall():
    rubric = RubricBreakdown.model_validate({
        "dimensions": [
            {"name": "a", "weight": 1.0, "meaning": "", "fail_cues": ""},
            {"name": "b", "weight": 1.0, "meaning": "", "fail_cues": ""},
        ],
        "det_weight": 0.4,
        "judge_weight": 0.6,
    })
    assert weighted_judge_overall({"a": 1.0, "b": 0.0}, rubric) == 0.5


@pytest.mark.unit
def test_evaluate_trajectory_wrapper(good_bundle: EvalBundle):
    out = evaluate_trajectory(good_bundle)
    assert "trajectory_score" in out
    assert out["trajectory_score"] >= 0.9


@pytest.mark.unit
def test_collect_trace_evidence_mock(monkeypatch):
    from evaluation.section_research.adapters import langsmith_pull as lsp

    class FakeChild:
        def __init__(self, name, run_type, inputs=None, outputs=None):
            self.name = name
            self.run_type = run_type
            self.inputs = inputs or {}
            self.outputs = outputs or {}
            self.error = None
            self.child_runs = []

    class FakeRoot:
        name = "section_research"
        inputs = {"ticker": "NVDA", "section_id": "3_business_model"}
        outputs = {
            "section_research_output": {
                "final_section_text": "x" * 100,
                "citations": [{"url": "https://example.com"}],
            },
            "evidence_ledger": [{"claim": "rev up", "source": "10-K"}],
        }
        child_runs = [
            FakeChild("web_search", "tool", {"query": "NVDA"}, {"hits": 1}),
        ]
        error = None

    class FakeClient:
        def read_run(self, run_id, load_child_runs=True):
            assert run_id == "run-123"
            return FakeRoot()

    packed = lsp.collect_trace_evidence("run-123", client=FakeClient())
    assert packed["final_state"]["ticker"] == "NVDA"
    assert packed["tool_outputs"]
    assert packed["evidence_ledger"]

    bundle = lsp.bundle_from_langsmith("run-123", client=FakeClient())
    assert bundle.source == "langsmith"
    assert bundle.run_id == "run-123"
    assert bundle.ticker == "NVDA"
