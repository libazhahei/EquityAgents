"""Financial Modeling Prep API client for earnings calls (not quotes)."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v3"


class FMPClient:
    """FMP integration for earnings call transcripts and related data."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        er = self.config.get("equity_research", {})
        self.api_key = os.environ.get("FMP_API_KEY", er.get("fmp_api_key", ""))
        self.daily_limit = int(er.get("fmp_daily_limit", 250))
        self._calls_today = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _get(self, path: str, params: dict | None = None) -> Any:
        if not self.api_key:
            return None
        if self._calls_today >= self.daily_limit:
            logger.warning("FMP daily limit reached")
            return None
        params = dict(params or {})
        params["apikey"] = self.api_key
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(f"{FMP_BASE}{path}", params=params)
                response.raise_for_status()
                self._calls_today += 1
                return response.json()
        except Exception as exc:
            logger.debug("FMP request failed: %s", exc)
            return None

    def fetch_earnings_call_transcripts(self, ticker: str, limit: int = 2) -> list[dict[str, Any]]:
        """Fetch recent earnings call transcripts for a ticker."""
        data = self._get(f"/earning_call_transcript/{ticker.upper()}", {"limit": limit})
        if not data:
            return []
        if isinstance(data, list):
            return [
                {
                    "ticker": ticker.upper(),
                    "date": item.get("date", ""),
                    "quarter": item.get("quarter"),
                    "year": item.get("year"),
                    "content": (item.get("content") or "")[:8000],
                }
                for item in data[:limit]
            ]
        return []

    def fetch_earnings_calendar(self, ticker: str) -> list[dict[str, Any]]:
        data = self._get("/historical/earning_calendar/" + ticker.upper())
        if isinstance(data, list):
            return data[:5]
        return []
