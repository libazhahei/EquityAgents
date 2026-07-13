"""Tests for step payload builder and skip-verify helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

from tradingagents.equity_research.runtime.nodes.section_executor import (
    _VERIFY_SKIP_SUMMARY,
    _should_skip_verify,
    create_section_executor_apply_node,
    create_section_executor_dispatch_node,
    section_executor_router,
)
from tradingagents.equity_research.runtime.utils.step_payload import (
    build_step_payload,
    format_step_payload_for_prompt,
)
from tradingagents.equity_research.tasks.section_research.profile import (
    SECTION_RESEARCH_TASK_PROFILE,
)


def test_build_verify_payload_filters_by_qid_and_metadata_status():
    state = {
        "section_id": "3_business_model",
        "active_task": {"question_id": "q2", "task_id": "t_q2"},
        "evidence_ledger": [
            {
                "evidence_id": "ev1",
                "question_id": "q2",
                "quote": "Revenue was $68B",
                "source": "10-Q",  # derived source_type
                "url": "https://example.com/10q",
                "period": "FY26 Q4",
            },
            {
                "evidence_id": "ev_other",
                "question_id": "q1",
                "quote": "should be excluded",
                "url": "https://example.com/other",
            },
        ],
        "claim_ledger": [
            {
                "claim_id": "c1",
                "claim": "Data center drove growth",
                "supporting_evidence_ids": ["ev1"],
            }
        ],
        "answer_cards": {
            "q2": {
                "quantified_claims": [{"metric": "revenue", "value_or_range": "68B"}],
                "source_attributions": [],
                "open_gaps": ["need platform"],
            }
        },
    }
    payload = build_step_payload(state, "verify")
    assert payload["status"] == "ok"
    assert payload["question_id"] == "q2"
    assert len(payload["evidence"]) == 1
    assert payload["evidence"][0]["evidence_id"] == "ev1"
    assert "https://example.com/10q" in payload["citation_urls"]
    assert payload["claims"][0]["claim_id"] == "c1"
    gap = payload["metadata_gaps"][0]
    assert gap["fields"]["source_type"]["status"] == "derived"
    assert gap["fields"]["platform"]["status"] == "missing"
    assert gap["fields"]["traceable_ref"]["status"] == "derived"
    assert payload["answer_card"]["open_gaps"] == ["need platform"]


def test_evidence_fallback_to_untagged_only():
    state = {
        "active_task": {"question_id": "q2"},
        "evidence_ledger": [
            {"evidence_id": "ev_untagged", "quote": "untagged", "url": "https://a.com"},
            {"evidence_id": "ev_q1", "question_id": "q1", "quote": "other q"},
        ],
    }
    payload = build_step_payload(state, "verify")
    assert payload["filter"]["evidence_fallback"] is True
    assert [e["evidence_id"] for e in payload["evidence"]] == ["ev_untagged"]


def test_empty_payload_status():
    payload = build_step_payload({"active_task": {"question_id": "q9"}}, "verify")
    assert payload["status"] == "empty"
    assert "no_evidence" in payload["gaps"]


def test_calculate_payload_shape():
    state = {
        "active_task": {"question_id": "q2"},
        "evidence_ledger": [
            {
                "evidence_id": "ev1",
                "question_id": "q2",
                "metric": "revenue",
                "value": "68",
                "quote": "x",
            }
        ],
        "calculation_store": [{"expression": "68*1.1", "result": 74.8}],
        "claim_ledger": [{"claim_id": "c1", "claim": "ignored for calc"}],
    }
    payload = build_step_payload(state, "calculate")
    assert "numeric_evidence" in payload
    assert "claims" not in payload
    assert "citation_urls" not in payload
    assert payload["numeric_evidence"][0]["metric"] == "revenue"
    assert len(payload["calculation_store"]) == 1


def test_truncation_caps():
    evidence = [
        {
            "evidence_id": f"ev{i}",
            "question_id": "q2",
            "quote": "q" * 500,
            "url": f"https://example.com/{i}",
        }
        for i in range(12)
    ]
    payload = build_step_payload(
        {"active_task": {"question_id": "q2"}, "evidence_ledger": evidence},
        "verify",
    )
    assert payload["truncated"] is True
    assert payload["omitted_counts"]["evidence"] == 4
    assert len(payload["evidence"]) == 8
    assert len(payload["evidence"][0]["quote"]) <= 240


def test_format_step_payload_for_prompt_contains_json():
    text = format_step_payload_for_prompt({"status": "empty", "gaps": ["no_evidence"]})
    assert "Step payload" in text
    assert '"status":"empty"' in text or '"status": "empty"' in text


def test_should_skip_verify_respects_config():
    step = {"action": "verify"}
    deps_on = SimpleNamespace(config={"equity_research": {"skip_verify": True}})
    deps_off = SimpleNamespace(config={"equity_research": {"skip_verify": False}})
    assert _should_skip_verify(deps_on, step) is True
    assert _should_skip_verify(deps_off, step) is False
    assert _should_skip_verify(deps_on, {"action": "search"}) is False


def test_dispatch_skip_verify_sets_flag_without_llm():
    deps = Mock()
    deps.config = {"equity_research": {"skip_verify": True}}
    deps.deep_llm = Mock()
    dispatch = create_section_executor_dispatch_node(deps, SECTION_RESEARCH_TASK_PROFILE)
    state = {
        "active_task": {"task_id": "t1", "question_id": "q2", "objective": "obj"},
        "active_step": {
            "step_id": "q2_s3",
            "action": "verify",
            "description": "Verify data",
            "status": "in_progress",
        },
        "messages": [],
        "research_plan": {
            "tasks": [
                {
                    "task_id": "t1",
                    "question_id": "q2",
                    "objective": "obj",
                    "status": "in_progress",
                    "steps": [
                        {
                            "step_id": "q2_s3",
                            "order": 3,
                            "action": "verify",
                            "description": "Verify data",
                            "status": "in_progress",
                        }
                    ],
                }
            ]
        },
    }
    out = dispatch(state)
    assert out.get("_verify_skipped") is True
    deps.deep_llm.bind_tools.assert_not_called()


def test_router_and_apply_mark_verify_skipped():
    deps = Mock()
    deps.config = {"equity_research": {"skip_verify": True}}
    deps.trace = Mock(return_value={})
    apply = create_section_executor_apply_node(deps, SECTION_RESEARCH_TASK_PROFILE)

    state = {
        "_verify_skipped": True,
        "messages": [],
        "active_task": {"task_id": "t1", "question_id": "q2"},
        "active_step": {"step_id": "q2_s3", "action": "verify"},
        "research_plan": {
            "tasks": [
                {
                    "task_id": "t1",
                    "question_id": "q2",
                    "objective": "obj",
                    "status": "in_progress",
                    "steps": [
                        {
                            "step_id": "q2_s1",
                            "order": 1,
                            "action": "search",
                            "description": "Search",
                            "status": "done",
                        },
                        {
                            "step_id": "q2_s3",
                            "order": 3,
                            "action": "verify",
                            "description": "Verify",
                            "status": "in_progress",
                        },
                    ],
                }
            ]
        },
        "research_todo_list": {
            "items": [
                {"item_id": "i1", "step_id": "q2_s3", "status": "in_progress"},
            ]
        },
    }
    assert section_executor_router(state) == "apply"
    out = apply(state)
    plan = out["research_plan"]
    step = plan["tasks"][0]["steps"][1]
    assert step["status"] == "skipped"
    assert step["result_summary"] == _VERIFY_SKIP_SUMMARY
    assert out["research_todo_list"]["items"][0]["status"] == "done"
    assert out.get("_verify_skipped") is False
    assert out.get("_force_synthesize") is not True
