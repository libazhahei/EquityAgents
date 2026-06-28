"""Tests for Perplexity LangChain tool wrapper."""

from unittest.mock import MagicMock

from tradingagents.equity_research.tools.perplexity_tool import (
    execute_perplexity_search,
    make_perplexity_search_tool,
)


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
