"""Tests for vendor chain routing."""

from __future__ import annotations

import pytest

from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)
from tradingagents.dataflows.vendor_routing import build_vendor_chain, execute_vendor_chain


def test_build_vendor_chain_respects_tool_vendors():
    config = {"tool_vendors": {"web_search": "jina"}}
    chain = build_vendor_chain(
        "web_search",
        {"tavily": lambda: None, "jina": lambda: None},
        category="web_search_data",
        config=config,
    )
    assert chain == ["jina"]


def test_build_vendor_chain_does_not_add_unconfigured_vendors():
    config = {"tool_vendors": {"web_search": "tavily"}}
    chain = build_vendor_chain(
        "web_search",
        {"tavily": lambda: None, "jina": lambda: None},
        category="web_search_data",
        config=config,
    )
    assert chain == ["tavily"]
    assert "jina" not in chain


def test_execute_vendor_chain_falls_back_on_not_configured():
    calls = []

    def primary():
        calls.append("primary")
        raise VendorNotConfiguredError("no key")

    def secondary():
        calls.append("secondary")
        return {"ok": True}

    result = execute_vendor_chain(
        "test",
        ["primary", "secondary"],
        {"primary": primary, "secondary": secondary},
        wrap_metadata=True,
    )
    assert calls == ["primary", "secondary"]
    assert result["ok"] is True
    assert result["vendor_used"] == "secondary"


def test_execute_vendor_chain_falls_back_on_rate_limit():
    def primary():
        raise VendorRateLimitError("limited")

    def secondary():
        return {"data": 1}

    result = execute_vendor_chain(
        "test",
        ["primary", "secondary"],
        {"primary": primary, "secondary": secondary},
        wrap_metadata=True,
    )
    assert result["data"] == 1
    assert result["vendor_used"] == "secondary"


def test_execute_vendor_chain_no_data_string_at_end():
    def primary():
        raise NoMarketDataError(symbol="X", detail="empty")

    def secondary():
        raise NoMarketDataError(symbol="X", detail="also empty")

    result = execute_vendor_chain(
        "get_stock_data",
        ["primary", "secondary"],
        {"primary": primary, "secondary": secondary},
    )
    assert isinstance(result, str)
    assert result.startswith("NO_DATA_AVAILABLE")


def test_execute_vendor_chain_wraps_list_results_with_vendor_used():
    def primary():
        raise NoMarketDataError(symbol="AAPL", detail="no transcripts")

    def secondary():
        return [{"ticker": "AAPL", "content": "transcript"}]

    result = execute_vendor_chain(
        "transcript_search",
        ["fmp", "perplexity"],
        {"fmp": primary, "perplexity": secondary},
        wrap_metadata=True,
    )
    assert result["vendor_used"] == "perplexity"
    assert result["fallback_attempted"] == ["fmp", "perplexity"]
    assert result["data"] == [{"ticker": "AAPL", "content": "transcript"}]


def test_execute_vendor_chain_falls_back_on_subscription_error():
    from tradingagents.dataflows.errors import VendorSubscriptionError

    def primary():
        raise VendorSubscriptionError("Restricted Endpoint")

    def secondary():
        return [{"ticker": "AAPL", "content": "perp transcript"}]

    result = execute_vendor_chain(
        "transcript_search",
        ["fmp", "perplexity"],
        {"fmp": primary, "perplexity": secondary},
        wrap_metadata=True,
    )
    assert result["vendor_used"] == "perplexity"
    assert result["fallback_attempted"] == ["fmp", "perplexity"]


def test_build_vendor_chain_transcript_search_prefers_alpha_vantage():
    from tradingagents.dataflows.vendor_routing import build_vendor_chain
    from tradingagents.equity_research.tools.interface import EQUITY_VENDOR_METHODS
    from tradingagents.dataflows.config import get_config

    chain = build_vendor_chain(
        "transcript_search",
        EQUITY_VENDOR_METHODS["transcript_search"],
        category="transcripts_data",
        config=get_config(),
        equity_override=True,
    )
    assert chain == ["alpha_vantage", "fmp", "perplexity"]


def test_execute_vendor_chain_raises_first_error_when_no_no_data():
    def primary():
        raise RuntimeError("network down")

    with pytest.raises(RuntimeError, match="network down"):
        execute_vendor_chain(
            "test",
            ["primary"],
            {"primary": primary},
        )
