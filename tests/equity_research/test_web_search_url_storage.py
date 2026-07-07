"""Tests for web_search URL fetch and document storage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tradingagents.equity_research.tools import search_tools


def _mock_deps(tmp_path: Path):
    deps = MagicMock()
    deps.config = {
        "data_cache_dir": str(tmp_path),
        "equity_research": {"web_search_max_url_fetches": 2},
    }
    deps.documents.register.side_effect = lambda **kwargs: {
        "doc_id": f"doc_{hash(kwargs.get('source_url', '')) & 0xffff:04x}",
        **kwargs,
    }
    return deps


def test_web_search_with_url_storage_registers_and_caches(tmp_path):
    deps = _mock_deps(tmp_path)
    search_result = {
        "query": "NVDA revenue",
        "results": [
            {"title": "NVDA News", "url": "https://example.com/a", "content": "snippet a"},
            {"title": "More", "url": "https://example.com/b", "content": "snippet b"},
            {"title": "Third", "url": "https://example.com/c", "content": "snippet c"},
        ],
    }

    with patch.object(search_tools, "web_search", return_value=search_result):
        with patch.object(
            search_tools,
            "web_fetch",
            side_effect=lambda url: {"url": url, "content": f"full text for {url}"},
        ):
            result = search_tools.web_search_with_url_storage(
                "NVDA revenue",
                deps=deps,
                ticker="NVDA",
            )

    assert result["api_calls"] == 3  # 1 search + 2 fetches (max 2)
    assert len(result["doc_ids"]) == 2
    assert result["results"][0]["doc_id"] == result["doc_ids"][0]
    assert deps.documents.register.call_count == 2
    cached = list((tmp_path / "equity_research" / "web" / "NVDA").glob("*.md"))
    assert len(cached) == 2


def test_web_search_without_deps_skips_fetch():
    search_result = {
        "query": "test",
        "results": [{"title": "T", "url": "https://example.com/x", "content": "s"}],
    }
    with patch.object(search_tools, "web_search", return_value=search_result):
        result = search_tools.web_search_with_url_storage("test")

    assert result["urls"] == ["https://example.com/x"]
    assert result["doc_ids"] == []
    assert result["api_calls"] == 1


def test_make_web_search_tool_uses_deps():
    from tradingagents.equity_research.tools.lc.search import make_web_search_tool

    deps = MagicMock()
    expected = {"query": "q", "doc_ids": ["doc_1"], "api_calls": 2}
    with patch.object(search_tools, "web_search_with_url_storage", return_value=expected) as mocked:
        tool = make_web_search_tool(deps)
        out = tool.invoke({"query": "q", "ticker": "AAPL"})
    assert out == expected
    mocked.assert_called_once_with("q", recency=None, deps=deps, ticker="AAPL")
    assert tool.name == "web_search"
