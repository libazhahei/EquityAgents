"""Tests for Alpha Vantage earnings transcript helpers."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from tradingagents.dataflows.alpha_vantage_transcript import (
    _from_av_quarter,
    _to_av_quarter,
    get_earnings_call_transcript,
)
from tradingagents.dataflows.errors import NoMarketDataError


def test_quarter_label_conversion():
    assert _to_av_quarter("Q1 2024") == "2024Q1"
    assert _to_av_quarter("2024Q3") == "2024Q3"
    assert _from_av_quarter("2024Q3") == "Q3 2024"


def test_get_earnings_call_transcript_returns_normalized_payload():
    payload = {
        "symbol": "AAPL",
        "quarter": "2024Q4",
        "transcript": [
            {"speaker": "CEO", "title": "Chief Executive Officer", "content": "Revenue grew."},
            {"speaker": "CFO", "content": "Margins improved."},
        ],
    }
    with patch(
        "tradingagents.dataflows.alpha_vantage_transcript._make_api_request",
        return_value=payload,
    ):
        data = get_earnings_call_transcript("AAPL", quarter="Q4 2024")

    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["quarter"] == "Q4 2024"
    assert "Revenue grew." in data[0]["content"]
    assert "Margins improved." in data[0]["content"]


def test_get_earnings_call_transcript_raises_when_empty():
    with patch(
        "tradingagents.dataflows.alpha_vantage_transcript._make_api_request",
        return_value={"symbol": "AAPL", "quarter": "2024Q4", "transcript": []},
    ), patch(
        "tradingagents.dataflows.alpha_vantage_transcript._recent_av_quarters",
        return_value=["2024Q4"],
    ):
        with pytest.raises(NoMarketDataError):
            get_earnings_call_transcript("AAPL")
