"""Tests for FMP earnings transcript client."""

from __future__ import annotations

from unittest.mock import patch

import httpx
import pytest

from tradingagents.equity_research.integrations.fmp import FMPClient, FMPSubscriptionError, _parse_quarter_label


def test_parse_quarter_label():
    assert _parse_quarter_label("Q1 2024") == (2024, 1)
    assert _parse_quarter_label("q3 2023") == (2023, 3)
    assert _parse_quarter_label(None) == (None, None)


def test_fmp_client_reads_daily_limit_from_env(monkeypatch):
    monkeypatch.setenv("FMP_API_KEY", "test-key")
    monkeypatch.setenv("FMP_DAYILY_LIMIT", "230")
    client = FMPClient({})
    assert client.daily_limit == 230


def test_fetch_earnings_call_transcripts_uses_stable_endpoint():
    client = FMPClient({"equity_research": {"fmp_api_key": "test-key"}})

    def fake_request(base, path, params=None):
        if path == "earning-call-transcript-dates":
            return [{"fiscalYear": 2024, "quarter": 4}]
        if path == "earning-call-transcript":
            return [{"symbol": "AAPL", "year": 2024, "quarter": 4, "content": "hello transcript"}]
        return None

    with patch.object(client, "_request", side_effect=fake_request):
        data = client.fetch_earnings_call_transcripts("AAPL")

    assert len(data) == 1
    assert data[0]["content"] == "hello transcript"
    assert data[0]["quarter"] == "Q4 2024"


def test_fetch_earnings_call_transcripts_raises_subscription_error_on_restricted_plan():
    client = FMPClient({"equity_research": {"fmp_api_key": "test-key"}})
    response = httpx.Response(
        402,
        json={"Error Message": "Restricted Endpoint"},
        request=httpx.Request("GET", "https://example.com"),
    )

    with patch.object(client, "_request", side_effect=FMPSubscriptionError("Restricted Endpoint")):
        data = client.fetch_earnings_call_transcripts("AAPL", quarter="Q4 2024")

    assert data == []


def test_request_raises_subscription_error_for_402():
    client = FMPClient({"equity_research": {"fmp_api_key": "test-key"}})

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, params=None):
            return httpx.Response(
                402,
                json={"Error Message": "Restricted Endpoint"},
                request=httpx.Request("GET", url),
            )

    with patch("tradingagents.equity_research.integrations.fmp.httpx.Client", FakeClient):
        with pytest.raises(FMPSubscriptionError, match="Restricted Endpoint"):
            client._get_stable("earning-call-transcript", {"symbol": "AAPL", "year": 2024, "quarter": 4})
