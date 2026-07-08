"""Tests for transcript_search vendor priority and metadata."""

from __future__ import annotations

import pytest

from tradingagents.dataflows.errors import NoMarketDataError, VendorNotConfiguredError
from tradingagents.equity_research.tools import interface


@pytest.fixture(autouse=True)
def _isolated_transcript_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(interface, "get_config", lambda: {"data_cache_dir": str(tmp_path)})


def test_transcript_search_prefers_alpha_vantage_before_fmp_and_perplexity():
    calls: list[str] = []

    def mock_alpha(ticker, quarter=None, query=None, **kwargs):
        calls.append("alpha_vantage")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_fmp(ticker, quarter=None, **kwargs):
        calls.append("fmp")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_perplexity(ticker, quarter=None, query=None, **kwargs):
        calls.append("perplexity")
        return [{"ticker": ticker, "quarter": quarter, "content": "perp transcript"}]

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": mock_alpha,
        "fmp": mock_fmp,
        "perplexity": mock_perplexity,
    }
    try:
        result = interface.route_equity_tool("transcript_search", "AAPL", quarter="Q1 2024")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert calls == ["alpha_vantage", "fmp", "perplexity"]
    assert result["vendor_used"] == "perplexity"
    assert result["fallback_attempted"] == ["alpha_vantage", "fmp", "perplexity"]


def test_transcript_search_prefers_fmp_and_reports_actual_vendor_on_fallback():
    calls: list[str] = []

    def mock_alpha(ticker, quarter=None, query=None, **kwargs):
        calls.append("alpha_vantage")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_fmp(ticker, quarter=None, **kwargs):
        calls.append("fmp")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_perplexity(ticker, quarter=None, query=None, **kwargs):
        calls.append("perplexity")
        return [{"ticker": ticker, "quarter": quarter, "content": "perp transcript"}]

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": mock_alpha,
        "fmp": mock_fmp,
        "perplexity": mock_perplexity,
    }
    try:
        result = interface.route_equity_tool("transcript_search", "AAPL", quarter="Q1 2024")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert calls == ["alpha_vantage", "fmp", "perplexity"]
    assert result["vendor_used"] == "perplexity"
    assert result["fallback_attempted"] == ["alpha_vantage", "fmp", "perplexity"]
    assert result["data"][0]["content"] == "perp transcript"


def test_transcript_search_uses_fmp_when_available():
    calls: list[str] = []

    def mock_alpha(ticker, quarter=None, query=None, **kwargs):
        calls.append("alpha_vantage")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_fmp(ticker, quarter=None, **kwargs):
        calls.append("fmp")
        return [{"ticker": ticker, "content": "fmp transcript"}]

    def mock_perplexity(ticker, quarter=None, query=None, **kwargs):
        calls.append("perplexity")
        return [{"ticker": ticker, "content": "perp transcript"}]

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": mock_alpha,
        "fmp": mock_fmp,
        "perplexity": mock_perplexity,
    }
    try:
        result = interface.route_equity_tool("transcript_search", "AAPL")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert calls == ["alpha_vantage", "fmp"]
    assert result["vendor_used"] == "fmp"
    assert result["data"][0]["content"] == "fmp transcript"


def test_transcript_search_falls_back_to_perplexity_on_fmp_subscription_error():
    from tradingagents.dataflows.errors import VendorSubscriptionError

    calls: list[str] = []

    def mock_alpha(ticker, quarter=None, query=None, **kwargs):
        calls.append("alpha_vantage")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_fmp(ticker, quarter=None, **kwargs):
        calls.append("fmp")
        raise VendorSubscriptionError("Restricted Endpoint")

    def mock_perplexity(ticker, quarter=None, query=None, **kwargs):
        calls.append("perplexity")
        return [{"ticker": ticker, "quarter": quarter, "content": "perp transcript"}]

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": mock_alpha,
        "fmp": mock_fmp,
        "perplexity": mock_perplexity,
    }
    try:
        result = interface.route_equity_tool("transcript_search", "AAPL", quarter="Q1 2024")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert calls == ["alpha_vantage", "fmp", "perplexity"]
    assert result["vendor_used"] == "perplexity"
    assert result["data"][0]["content"] == "perp transcript"


def test_transcript_search_skips_unconfigured_fmp_before_perplexity():
    calls: list[str] = []

    def mock_alpha(ticker, quarter=None, query=None, **kwargs):
        calls.append("alpha_vantage")
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")

    def mock_fmp(ticker, quarter=None, **kwargs):
        calls.append("fmp")
        raise VendorNotConfiguredError("FMP_API_KEY is not set")

    def mock_perplexity(ticker, quarter=None, query=None, **kwargs):
        calls.append("perplexity")
        return [{"ticker": ticker, "content": "perp transcript"}]

    original = interface.EQUITY_VENDOR_METHODS["transcript_search"].copy()
    interface.EQUITY_VENDOR_METHODS["transcript_search"] = {
        "alpha_vantage": mock_alpha,
        "fmp": mock_fmp,
        "perplexity": mock_perplexity,
    }
    try:
        result = interface.route_equity_tool("transcript_search", "AAPL")
    finally:
        interface.EQUITY_VENDOR_METHODS["transcript_search"] = original

    assert calls == ["alpha_vantage", "fmp", "perplexity"]
    assert result["vendor_used"] == "perplexity"
