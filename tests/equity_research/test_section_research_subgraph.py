"""Tests for SectionResearchSubgraph topology and helpers."""

from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, ToolMessage

from tradingagents.equity_research.runtime.nodes.section_executor import section_executor_router
from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.runtime.utils.context_compact import clear_compact_cache, compact_if_needed
from tradingagents.equity_research.runtime.utils.llm_resolve import is_quick_research, resolve_research_llm
from tradingagents.equity_research.tasks.section_research.memory_seed import seed_parent_memory_into_subgraph
from tradingagents.equity_research.tasks.section_research.planning import expand_outline_to_plan
from tradingagents.equity_research.tasks.section_research.profile import (
    EXECUTOR_LANGCHAIN_TOOL_NAMES,
    SECTION_RESEARCH_TASK_PROFILE,
)
from tradingagents.equity_research.tasks.section_research.schemas import (
    PlannerTaskOutline,
    SectionResearchPlanOutlineLLMOutput,
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
    assert len(plan.tasks[0].steps) == 3
    assert plan.tasks[0].steps[0].action == "orient"
    assert plan.tasks[0].steps[-1].action == "synthesize"


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
