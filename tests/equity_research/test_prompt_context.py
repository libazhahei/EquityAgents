"""Tests for prompt context assemble/compact and executor dialogue slim-down."""

from __future__ import annotations

from unittest.mock import MagicMock

from langchain_core.messages import ToolMessage

from tradingagents.equity_research.runtime.nodes.section_executor import (
    _ingest_and_slim_tool_messages,
    _is_slimmed_tool_content,
)
from tradingagents.equity_research.runtime.utils.context_compact import (
    assemble_and_compact_context,
    assemble_context_block,
    clear_compact_cache,
    compact_if_needed,
    resolve_prompt_context_max_chars,
)
from tradingagents.equity_research.runtime.utils.executor_context import (
    slim_tool_message_content,
)
from tradingagents.equity_research.runtime.utils.search_memory import format_search_memory


def test_resolve_prompt_context_max_chars_prefers_new_key():
    config = {"equity_research": {"prompt_context_max_chars": 32000, "consensus_context_max_chars": 10}}
    assert resolve_prompt_context_max_chars(config) == 32000


def test_assemble_context_block_skips_empty():
    text = assemble_context_block({"A": "hello", "B": "", "C": "world"})
    assert "### A" in text
    assert "hello" in text
    assert "### C" in text
    assert "### B" not in text


def test_assemble_and_compact_short_circuits_without_llm():
    clear_compact_cache()
    deps = MagicMock()
    deps.config = {"equity_research": {"prompt_context_max_chars": 32000}}
    nano = MagicMock()
    deps.nano_llm = nano
    result = assemble_and_compact_context(
        deps,
        {"View": "short context"},
        purpose="unit-test",
    )
    assert "short context" in result
    nano.invoke.assert_not_called()


def test_assemble_and_compact_compacts_once_when_over_budget():
    clear_compact_cache()
    deps = MagicMock()
    deps.config = {"equity_research": {"prompt_context_max_chars": 50}}
    nano = MagicMock()
    nano.model_name = "nano-test"
    response = MagicMock()
    response.content = "compressed-once"
    nano.invoke.return_value = response
    deps.nano_llm = nano
    deps.quick_llm = nano

    result = assemble_and_compact_context(
        deps,
        {
            "View": "x" * 40,
            "Memory": "y" * 40,
        },
        purpose="unit-test-once",
    )
    assert result == "compressed-once"
    assert nano.invoke.call_count == 1


def test_format_search_memory_prefers_full_answer():
    records = [{
        "iteration": 1,
        "target_dimension": "kpi_focus",
        "mode": "targeted",
        "query": "q",
        "answer": "FULL ANSWER TEXT",
        "answer_summary": "short summary",
    }]
    text = format_search_memory(records, prefer_full_answer=True)
    assert "FULL ANSWER TEXT" in text
    assert "short summary" not in text

    slim = format_search_memory(records, prefer_full_answer=False)
    assert "short summary" in slim


def test_slim_tool_message_and_ingest_preserves_evidence():
    full_payload = {
        "items": [{
            "evidence": {
                "snippet": "Revenue grew 20% YoY in FY2024",
                "source": "10-K",
                "question_id": "q1",
            }
        }],
        "answer": "Long answer that should not stay in dialogue",
    }
    import json
    msg = ToolMessage(
        content=json.dumps(full_payload),
        tool_call_id="call_1",
        name="web_search",
        id="msg-1",
    )
    state = {
        "active_task": {"question_id": "q1"},
        "research_todo_list": {"items": []},
    }
    slimmed, evidence, updates = _ingest_and_slim_tool_messages([msg], state)
    assert evidence, "full tool payload should become pending evidence"
    assert any("Revenue grew 20%" in str(ev.get("snippet") or ev.get("content") or "") for ev in evidence)
    assert len(slimmed) == 1
    assert _is_slimmed_tool_content(slimmed[0].content)
    parsed = json.loads(str(slimmed[0].content))
    assert parsed["slimmed"] is True
    assert "summary" in parsed
    assert "Long answer that should not stay in dialogue" not in parsed["summary"] or len(parsed["summary"]) < len(
        full_payload["answer"]
    ) + 50
    assert updates.get("_slimmed_tool_messages")
    assert slimmed[0].id == "msg-1"


def test_slim_tool_message_content_helper():
    import json
    slim = slim_tool_message_content(json.dumps({"summary": "ok", "items": []}), tool_name="x")
    data = json.loads(slim)
    assert data["slimmed"] is True
    assert data["tool"] == "x"
