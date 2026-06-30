"""Tests for Perplexity LangChain tool wrapper."""

import json
from unittest.mock import MagicMock

from tradingagents.equity_research.tools.lc.search import make_batch_perplexity_search_tool
from tradingagents.equity_research.tools.perplexity_tool import (
    execute_perplexity_search,
    make_perplexity_search_tool,
)
from tradingagents.equity_research.tools.registry import ToolRegistry


def test_make_perplexity_search_tool_returns_json_evidence():
    deps = MagicMock()
    deps.perplexity.api_key = "test-key"
    deps.perplexity.search.return_value = {
        "answer": "NVDA consensus revenue growth 20%",
        "citations": ["https://example.com/nvda"],
    }
    deps.documents.register.return_value = {"doc_id": "doc_1"}

    tool = make_perplexity_search_tool(deps)
    raw = tool.invoke({
        "ticker": "NVDA",
        "query": "NVDA analyst consensus revenue estimates",
        "target_dimension": "quantitative_estimates",
        "mode": "targeted",
    })
    assert "NVDA consensus" in raw
    assert "https://example.com/nvda" in raw
    deps.perplexity.search.assert_called_once()


def test_execute_perplexity_search_still_used_by_executor_path():
    deps = MagicMock()
    deps.perplexity.api_key = "test-key"
    deps.perplexity.search.return_value = {
        "answer": "data",
        "citations": ["https://example.com/a"],
    }
    deps.documents.register.return_value = {"doc_id": "doc_2"}

    evidence = execute_perplexity_search(
        deps,
        query="NVDA KPI focus",
        mode="exploratory",
        target_dimension="kpi_focus",
        ticker="NVDA",
    )
    assert evidence.answer == "data"
    assert evidence.citations == ["https://example.com/a"]


def test_make_batch_perplexity_search_tool_returns_json_batch_result():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.perplexity.api_key = "test-key"
    deps.perplexity.search.return_value = {
        "answer": "batch answer",
        "citations": ["https://example.com/batch"],
    }
    deps.documents.register.return_value = {"doc_id": "doc_batch"}
    deps.quick_llm.invoke.return_value = MagicMock(content="summary")

    tool = make_batch_perplexity_search_tool(deps)
    raw = tool.invoke({
        "ticker": "NVDA",
        "queries": [
            {"query": "NVDA estimates", "target_dimension": "quantitative_estimates", "mode": "targeted"},
        ],
        "iteration": 0,
        "search_memory": None,
    })
    payload = json.loads(raw)
    assert len(payload["items"]) == 1
    assert payload["items"][0]["evidence"]["answer"] == "batch answer"
    deps.perplexity.search.assert_called_once()


def test_tool_registry_registers_batch_perplexity_search_with_deps():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    registry = ToolRegistry(deps)
    assert "batch_perplexity_search" in registry.list_tools()
    assert registry.get_langchain_tool("batch_perplexity_search").name == "batch_perplexity_search"
