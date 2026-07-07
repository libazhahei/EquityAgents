"""Tests for earnings transcript disk cache."""

from __future__ import annotations

from tradingagents.equity_research.integrations.transcript_cache import (
    cache_input_for_lookup,
    cache_input_for_store,
    get_cached_transcript_search,
    normalize_transcript_input,
    set_cached_transcript_search,
)
from tradingagents.equity_research.tools import interface


def test_normalize_transcript_input_unifies_quarter_formats():
    assert normalize_transcript_input("aapl", quarter="q1 2024") == {
        "ticker": "AAPL",
        "quarter": "Q1 2024",
        "query": None,
    }
    assert normalize_transcript_input("AAPL", quarter="2024Q1") == {
        "ticker": "AAPL",
        "quarter": "Q1 2024",
        "query": None,
    }


def test_non_perplexity_cache_ignores_query_on_store_and_lookup(tmp_path):
    config = {"data_cache_dir": str(tmp_path)}
    result = {
        "data": [{"ticker": "AAPL", "content": "cached transcript"}],
        "vendor_used": "alpha_vantage",
        "fallback_attempted": ["alpha_vantage"],
    }
    set_cached_transcript_search(
        config,
        "AAPL",
        quarter="Q1 2024",
        query="margin",
        result=result,
    )

    assert get_cached_transcript_search(
        config,
        "AAPL",
        quarter="2024Q1",
        query="  Margin ",
    ) is None

    cached = get_cached_transcript_search(config, "AAPL", quarter="Q1 2024")
    assert cached is not None
    assert cached["cached"] is True
    assert cached["vendor_used"] == "alpha_vantage"


def test_perplexity_cache_matches_query(tmp_path):
    config = {"data_cache_dir": str(tmp_path)}
    result = {
        "data": [{"ticker": "AAPL", "content": "perp transcript"}],
        "vendor_used": "perplexity",
        "fallback_attempted": ["alpha_vantage", "fmp", "perplexity"],
    }
    set_cached_transcript_search(
        config,
        "AAPL",
        quarter="Q1 2024",
        query="margin outlook",
        result=result,
    )

    cached = get_cached_transcript_search(
        config,
        "AAPL",
        quarter="Q1 2024",
        query="margin outlook",
    )
    assert cached is not None
    assert cached["vendor_used"] == "perplexity"

    assert get_cached_transcript_search(
        config,
        "AAPL",
        quarter="Q1 2024",
        query="pricing",
    ) is None

    assert get_cached_transcript_search(config, "AAPL", quarter="Q1 2024") is None


def test_cache_input_helpers():
    assert cache_input_for_lookup("AAPL", quarter="Q1 2024", query="margin") == {
        "ticker": "AAPL",
        "quarter": "Q1 2024",
        "query": "margin",
    }
    assert cache_input_for_lookup("AAPL", quarter="Q1 2024") == {
        "ticker": "AAPL",
        "quarter": "Q1 2024",
        "query": None,
    }
    assert cache_input_for_store(
        "AAPL",
        quarter="Q1 2024",
        query="margin",
        result={"vendor_used": "fmp", "data": [{}]},
    ) == {
        "ticker": "AAPL",
        "quarter": "Q1 2024",
        "query": None,
    }
    assert cache_input_for_store(
        "AAPL",
        quarter="Q1 2024",
        query="margin",
        result={"vendor_used": "perplexity", "data": [{}]},
    ) == {
        "ticker": "AAPL",
        "quarter": "Q1 2024",
        "query": "margin",
    }


def test_route_equity_tool_uses_transcript_cache_without_calling_vendors(tmp_path, monkeypatch):
    config = {"data_cache_dir": str(tmp_path)}
    monkeypatch.setattr(interface, "get_config", lambda: config)

    stored = {
        "data": [{"ticker": "AAPL", "content": "from cache"}],
        "vendor_used": "fmp",
        "fallback_attempted": ["fmp"],
    }
    set_cached_transcript_search(config, "AAPL", quarter="Q2 2024", result=stored)

    calls: list[str] = []

    def boom(*args, **kwargs):
        calls.append("vendor")
        raise AssertionError("vendor chain should not run on cache hit")

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": boom,
        "fmp": boom,
        "perplexity": boom,
    }
    try:
        result = interface.route_equity_tool("transcript_search", "AAPL", quarter="Q2 2024")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert calls == []
    assert result["cached"] is True
    assert result["data"][0]["content"] == "from cache"


def test_route_equity_tool_writes_transcript_cache_on_success(tmp_path, monkeypatch):
    config = {"data_cache_dir": str(tmp_path)}
    monkeypatch.setattr(interface, "get_config", lambda: config)

    def mock_alpha(ticker, quarter=None, query=None, **kwargs):
        return [{"ticker": ticker, "content": "fresh transcript"}]

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": mock_alpha,
        "fmp": lambda *a, **k: [],
        "perplexity": lambda *a, **k: [],
    }
    try:
        first = interface.route_equity_tool("transcript_search", "MSFT", quarter="Q3 2024")
        second = interface.route_equity_tool("transcript_search", "MSFT", quarter="Q3 2024")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert first.get("cached") is not True
    assert second["cached"] is True
    assert second["data"][0]["content"] == "fresh transcript"
