"""Tests for SectionResearchSubgraph topology and helpers."""

import json
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, ToolMessage

from tradingagents.equity_research.runtime.nodes.section_executor import (
    create_section_executor_apply_node,
    section_executor_router,
)
from tradingagents.equity_research.runtime.nodes.section_reflector import section_reflector_router
from tradingagents.equity_research.runtime.nodes.synthesizer import create_synthesizer_node
from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.runtime.utils.context_compact import clear_compact_cache, compact_if_needed
from tradingagents.equity_research.runtime.utils.llm_resolve import is_quick_research, resolve_research_llm
from tradingagents.equity_research.tasks.section_research.memory_seed import seed_parent_memory_into_subgraph
from tradingagents.equity_research.tasks.section_research.merge import collect_evidence_for_question
from tradingagents.equity_research.tasks.section_research.planning import expand_outline_to_plan
from tradingagents.equity_research.tasks.section_research.profile import (
    EXECUTOR_LANGCHAIN_TOOL_NAMES,
    SECTION_RESEARCH_TASK_PROFILE,
)
from tradingagents.equity_research.tasks.section_research.schemas import (
    PlannerTaskOutline,
    SectionResearchPlanOutlineLLMOutput,
    SectionResearchViewUpdate,
)


def test_section_subgraph_nodes():
    deps = MagicMock()
    graph = SectionResearchSubgraph(deps, SECTION_RESEARCH_TASK_PROFILE).build()
    nodes = set(graph.nodes.keys())
    assert "initial_planner" in nodes
    assert "executor" in nodes
    assert "executor_apply" in nodes
    assert "reflector" in nodes
    assert "loop_planner" in nodes
    assert "executor_tools_retrieval" in nodes
    assert "executor_tools_computation" in nodes
    assert "executor_tools_action" in nodes
    assert "executor_tool_router" not in nodes


def test_executor_tool_names_in_profile():
    assert "list_research_todos" in EXECUTOR_LANGCHAIN_TOOL_NAMES
    assert "filings_search" in EXECUTOR_LANGCHAIN_TOOL_NAMES


def test_expand_outline_to_plan():
    outline = SectionResearchPlanOutlineLLMOutput(
        plan_rationale="test",
        tasks=[
            PlannerTaskOutline(
                task_id="t_q1",
                question_id="q1",
                objective="Understand revenue drivers",
                approach="Search filings and earnings transcripts",
            ),
        ],
        execution_order=["t_q1"],
    )
    brief = {
        "questions": [{"id": "q1", "question": "Revenue?", "priority": 1, "expected_output": "Segments"}],
    }
    plan = expand_outline_to_plan(outline, brief, section_id="section_3")
    assert len(plan.tasks) == 1
    assert len(plan.tasks[0].steps) == 4
    assert plan.tasks[0].steps[0].action == "orient"
    assert plan.tasks[0].steps[-2].action == "synthesize"
    assert plan.tasks[0].steps[-1].action == "verify"


def test_quick_research_resolves_deep_to_quick():
    deps = MagicMock()
    deps.quick_llm = "quick"
    deps.deep_llm = "deep"
    deps.nano_llm = "nano"
    deps.config = {"equity_research": {"quick_research": True}}
    assert resolve_research_llm(deps, "deep") == "quick"
    deps.config = {"equity_research": {"quick_research": False}}
    assert resolve_research_llm(deps, "deep") == "deep"
    assert resolve_research_llm(deps, "nano") == "nano"
    assert is_quick_research({"equity_research": {"quick_research": True}})


def test_section_executor_router_routes_to_tool_group():
    state = {
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "steps": [{"step_id": "s1", "status": "in_progress", "action": "search"}],
                "status": "in_progress",
            }],
        },
        "active_task": {"task_id": "t1", "question_id": "q1"},
        "active_step": {"step_id": "s1", "action": "search", "tool_hints": ["web_search"]},
        "messages": [
            AIMessage(content="", tool_calls=[{"id": "tc1", "name": "web_search", "args": {}}]),
        ],
        "_executor_step_calls": 1,
        "_executor_max_calls": 6,
    }
    assert section_executor_router(state) == "executor_tools_retrieval"


def test_section_executor_router_applies_at_max_calls():
    state = {
        "active_task": {"task_id": "t1"},
        "active_step": {"step_id": "s1"},
        "messages": [
            AIMessage(content="", tool_calls=[{"id": "tc1", "name": "web_search", "args": {}}]),
        ],
        "_executor_step_calls": 6,
        "_executor_max_calls": 6,
    }
    assert section_executor_router(state) == "apply"


def test_section_executor_router_continue_after_tool():
    state = {
        "active_task": {"task_id": "t1"},
        "active_step": {"step_id": "s1"},
        "messages": [ToolMessage(content="ok", tool_call_id="tc1")],
        "_executor_step_calls": 2,
        "_executor_max_calls": 6,
    }
    assert section_executor_router(state) == "continue"


def _apply_state_base(**overrides):
    base = {
        "active_task": {"task_id": "t1", "question_id": "q1"},
        "active_step": {"step_id": "s1", "action": "search"},
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "status": "in_progress",
                "steps": [{"step_id": "s1", "status": "in_progress", "action": "search"}],
            }],
        },
        "messages": [],
        "evidence_buffer": [],
        "pending_evidence": [],
        "errors": [],
    }
    base.update(overrides)
    return base


def _mock_apply_deps():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.trace.return_value = {}
    return deps


def test_apply_ingests_web_search_results():
    deps = _mock_apply_deps()
    apply = create_section_executor_apply_node(deps, SECTION_RESEARCH_TASK_PROFILE)
    payload = {
        "results": [
            {"title": "NVDA revenue", "content": "Data center grew 90%", "url": "https://example.com"},
        ],
        "api_calls": 1,
    }
    state = _apply_state_base(
        messages=[ToolMessage(content=json.dumps(payload), tool_call_id="tc1")],
    )
    result = apply(state)
    assert len(result["pending_evidence"]) == 1
    assert result["pending_evidence"][0]["question_id"] == "q1"
    assert "Data center" in result["pending_evidence"][0]["snippet"]


def test_apply_ingests_batch_perplexity_items():
    deps = _mock_apply_deps()
    apply = create_section_executor_apply_node(deps, SECTION_RESEARCH_TASK_PROFILE)
    payload = {
        "items": [{
            "evidence": {
                "snippet": "Perplexity hit",
                "source": "web",
                "evidence_id": "ev_p1",
            },
        }],
        "api_calls": 1,
    }
    state = _apply_state_base(
        messages=[ToolMessage(content=json.dumps(payload), tool_call_id="tc1")],
    )
    result = apply(state)
    assert len(result["pending_evidence"]) == 1
    assert result["pending_evidence"][0]["evidence_id"] == "ev_p1"


def test_apply_ingests_store_evidence():
    deps = _mock_apply_deps()
    apply = create_section_executor_apply_node(deps, SECTION_RESEARCH_TASK_PROFILE)
    payload = {
        "evidence_fragments": [{
            "fragment_id": "frag1",
            "quote": "Stored fragment text",
            "source": "10-K",
        }],
        "evidence_id": "frag1",
    }
    state = _apply_state_base(
        messages=[ToolMessage(content=json.dumps(payload), tool_call_id="tc1")],
    )
    result = apply(state)
    assert len(result["pending_evidence"]) == 1
    assert "Stored fragment" in result["pending_evidence"][0]["snippet"]
    assert len(result["evidence_fragments"]) == 1


def test_executor_router_synthesize_short_circuits():
    state = {
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "steps": [{"step_id": "s3", "status": "in_progress", "action": "synthesize"}],
                "status": "in_progress",
            }],
        },
        "active_task": {"task_id": "t1", "question_id": "q1"},
        "active_step": {"step_id": "s3", "action": "synthesize"},
        "messages": [],
    }
    assert section_executor_router(state) == "apply"


def test_collect_evidence_for_question_dedupes_sources():
    state = {
        "pending_evidence": [{"evidence_id": "e1", "snippet": "a", "question_id": "q1"}],
        "evidence_buffer": [{"evidence_id": "e1", "snippet": "a", "question_id": "q1"}],
        "evidence_ledger": [{"evidence_id": "e2", "quote": "b", "question_id": "q1"}],
    }
    collected = collect_evidence_for_question(state, "q1")
    assert len(collected) == 2


def test_reflector_pending_tasks_override_llm_exit():
    """Pending-tasks-and-budget hard guard overrides LLM exit signal → executor."""
    state = {
        "coverage_report": {"recommended_next_action": "exit", "routing_decision": "exit"},
        "iterations": 1,
        "max_iterations": 5,
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "status": "in_progress",
                "steps": [
                    {"step_id": "s1", "status": "done", "action": "search"},
                    {"step_id": "s2", "status": "pending", "action": "verify"},
                ],
            }],
        },
        "research_todo_list": {"items": []},
    }
    assert section_reflector_router(state) == "run_existing_queue"


def test_reflector_respects_exit_when_pending_and_at_max_iter():
    """Explicit exit still wins when all questions exhausted their per-question budget."""
    state = {
        "coverage_report": {"recommended_next_action": "exit"},
        "iterations": 5,
        "max_iterations": 3,
        "question_iterations": {"q1": 3},  # q1 has exhausted its budget
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "status": "in_progress",
                "steps": [{"step_id": "s1", "status": "pending", "action": "search"}],
            }],
        },
        "research_todo_list": {"items": []},
    }
    assert section_reflector_router(state) == "exit"

def test_reflector_router_allows_exit_when_plan_complete():
    state = {
        "coverage_report": {"recommended_next_action": "exit", "routing_decision": "exit"},
        "iterations": 2,
        "max_iterations": 5,
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "status": "done",
                "steps": [{"step_id": "s1", "status": "done", "action": "search"}],
            }],
        },
        "research_todo_list": {"items": []},
    }
    assert section_reflector_router(state) == "exit"


def test_reflector_routes_to_loop_planner_on_plan_more():
    """When LLM recommends plan_more, router goes to loop_planner."""
    state = {
        "coverage_report": {"recommended_next_action": "plan_more", "routing_decision": "continue"},
        "iterations": 2,
        "max_iterations": 5,
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "status": "done",
                "steps": [{"step_id": "s1", "status": "done", "action": "search"}],
            }],
        },
        "research_todo_list": {"items": []},
    }
    assert section_reflector_router(state) == "plan_more"


def test_reflector_routes_to_executor_on_run_existing_queue():
    """When LLM recommends run_existing_queue, router goes to executor."""
    state = {
        "coverage_report": {"recommended_next_action": "run_existing_queue", "routing_decision": "continue"},
        "iterations": 2,
        "max_iterations": 5,
        "research_plan": {
            "tasks": [{
                "task_id": "t1",
                "question_id": "q1",
                "status": "in_progress",
                "steps": [
                    {"step_id": "s1", "status": "done", "action": "search"},
                    {"step_id": "s2", "status": "pending", "action": "verify"},
                ],
            }],
        },
        "research_todo_list": {"items": []},
    }
    assert section_reflector_router(state) == "run_existing_queue"


def test_synthesizer_force_run_on_synthesize_step():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.trace.return_value = {}
    mock_update = SectionResearchViewUpdate(ticker="NVDA")
    with patch(
        "tradingagents.equity_research.runtime.nodes.synthesizer.invoke_structured_with_retry",
        return_value=mock_update,
    ) as mock_invoke:
        synthesizer = create_synthesizer_node(deps, SECTION_RESEARCH_TASK_PROFILE)
        state = {
            "ticker": "NVDA",
            "section_id": "3_business_model",
            "structured_view": {
                "ticker": "NVDA",
                "section_id": "3_business_model",
                "answer_cards": {},
            },
            "pending_evidence": [],
            "evidence_buffer": [{"evidence_id": "e1", "snippet": "buffered", "question_id": "q1"}],
            "active_task": {"question_id": "q1"},
            "active_step": {"action": "synthesize"},
            "_force_synthesize": True,
        }
        synthesizer(state)
        mock_invoke.assert_called_once()


def test_compact_if_needed_short_circuits():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    assert compact_if_needed(deps, "short", purpose="test") == "short"


def test_compact_cache_reuse():
    clear_compact_cache()
    deps = MagicMock()
    deps.config = {"equity_research": {"consensus_context_max_chars": 10}}
    nano = MagicMock()
    nano.model_name = "nano-test"
    response = MagicMock()
    response.content = "compressed"
    nano.invoke.return_value = response
    deps.nano_llm = nano
    deps.quick_llm = nano
    long_text = "x" * 100
    first = compact_if_needed(deps, long_text, purpose="cache-test")
    second = compact_if_needed(deps, long_text, purpose="cache-test")
    assert first == second == "compressed"
    assert nano.invoke.call_count == 1


def test_seed_parent_memory_consensus():
    parent = {
        "ticker": "AAPL",
        "consensus_view": {
            "ticker": "AAPL",
            "summary": "Bullish consensus",
            "dimension_coverage": {},
        },
        "assumption_view": {
            "assumption_map": [{
                "id": "a1",
                "statement": "Revenue grows 10%",
                "category": "revenue",
            }],
        },
    }
    seeded = seed_parent_memory_into_subgraph(parent)
    assert len(seeded.get("consensus_ledger", [])) >= 1
    assert len(seeded.get("assumption_ledger", [])) >= 1
