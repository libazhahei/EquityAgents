"""Alpha Vantage earnings call transcript helpers."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any

from tradingagents.dataflows.alpha_vantage_common import _make_api_request
from tradingagents.dataflows.errors import NoMarketDataError


def _to_av_quarter(quarter: str | None) -> str | None:
    if not quarter:
        return None
    label = quarter.strip()
    match = re.match(r"Q\s*([1-4])\s*(\d{4})", label, flags=re.IGNORECASE)
    if match:
        return f"{match.group(2)}Q{match.group(1)}"
    match = re.match(r"(\d{4})Q([1-4])", label, flags=re.IGNORECASE)
    if match:
        return f"{match.group(1)}Q{match.group(2)}"
    return None


def _from_av_quarter(quarter: str) -> str:
    match = re.match(r"(\d{4})Q([1-4])", quarter, flags=re.IGNORECASE)
    if match:
        return f"Q{match.group(2)} {match.group(1)}"
    return quarter


def _recent_av_quarters(limit: int = 4) -> list[str]:
    today = date.today()
    year = today.year
    quarter = (today.month - 1) // 3 + 1
    labels: list[str] = []
    y, q = year, quarter
    for _ in range(limit):
        labels.append(f"{y}Q{q}")
        q -= 1
        if q < 1:
            q = 4
            y -= 1
    return labels


def _parse_transcript_payload(ticker: str, payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []
    segments = payload.get("transcript") or []
    if not segments:
        return []
    content_parts: list[str] = []
    for segment in segments:
        if not isinstance(segment, dict):
            continue
        text = str(segment.get("content") or "").strip()
        if not text:
            continue
        speaker = str(segment.get("speaker") or "").strip()
        title = str(segment.get("title") or "").strip()
        prefix = speaker or title
        content_parts.append(f"{prefix}: {text}" if prefix else text)
    if not content_parts:
        return []
    quarter = str(payload.get("quarter") or "")
    return [{
        "ticker": ticker.upper(),
        "quarter": _from_av_quarter(quarter) if quarter else None,
        "content": "\n\n".join(content_parts)[:8000],
    }]


def _fetch_transcript_for_quarter(ticker: str, quarter: str) -> list[dict[str, Any]]:
    payload = _make_api_request(
        "EARNINGS_CALL_TRANSCRIPT",
        {"symbol": ticker.upper(), "quarter": quarter},
    )
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []
    return _parse_transcript_payload(ticker, payload)


def get_earnings_call_transcript(
    ticker: str,
    *,
    quarter: str | None = None,
    max_attempts: int = 4,
) -> list[dict[str, Any]]:
    """Fetch earnings call transcript data from Alpha Vantage."""
    av_quarter = _to_av_quarter(quarter)
    quarters = [av_quarter] if av_quarter else _recent_av_quarters(max_attempts)
    for candidate in quarters:
        if not candidate:
            continue
        data = _fetch_transcript_for_quarter(ticker, candidate)
        if data:
            return data
    raise NoMarketDataError(symbol=ticker, detail="no alpha vantage transcripts")
