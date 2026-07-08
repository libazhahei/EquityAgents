"""Financial Modeling Prep API client for earnings calls (not quotes)."""

from __future__ import annotations

import logging
import os
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FMP_BASE = "https://financialmodelingprep.com/api/v3"
FMP_STABLE_BASE = "https://financialmodelingprep.com/stable"


class FMPSubscriptionError(Exception):
    """FMP plan does not include the requested endpoint."""


def _parse_quarter_label(quarter: str | None) -> tuple[int | None, int | None]:
    if not quarter:
        return None, None
    match = re.search(r"Q\s*([1-4])\s*(\d{4})", quarter, flags=re.IGNORECASE)
    if not match:
        return None, None
    return int(match.group(2)), int(match.group(1))


class FMPClient:
    """FMP integration for earnings call transcripts and related data."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        er = self.config.get("equity_research", {})
        self.api_key = os.environ.get("FMP_API_KEY", er.get("fmp_api_key", ""))
        env_limit = (
            os.environ.get("FMP_DAILY_LIMIT")
            or os.environ.get("FMP_DAYILY_LIMIT")
        )
        self.daily_limit = int(env_limit or er.get("fmp_daily_limit", 250))
        self._calls_today = 0

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _request(self, base: str, path: str, params: dict | None = None) -> Any:
        if not self.api_key:
            return None
        if self._calls_today >= self.daily_limit:
            logger.warning("FMP daily limit reached (%s)", self.daily_limit)
            return None
        params = dict(params or {})
        params["apikey"] = self.api_key
        url = f"{base.rstrip('/')}/{path.lstrip('/')}"
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.get(url, params=params)
                self._calls_today += 1
                if response.status_code in {402, 403}:
                    detail = self._error_detail(response)
                    logger.warning("FMP transcript endpoint unavailable (%s): %s", response.status_code, detail)
                    raise FMPSubscriptionError(detail)
                response.raise_for_status()
                return response.json()
        except FMPSubscriptionError:
            raise
        except Exception as exc:
            logger.warning("FMP request failed for %s: %s", path, exc)
            return None

    @staticmethod
    def _error_detail(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except Exception:
            return response.text[:200] or f"HTTP {response.status_code}"
        if isinstance(payload, dict):
            return str(payload.get("Error Message") or payload.get("message") or payload)[:300]
        return str(payload)[:300]

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._request(FMP_BASE, path, params=params)

    def _get_stable(self, path: str, params: dict | None = None) -> Any:
        return self._request(FMP_STABLE_BASE, path, params=params)

    def _normalize_transcript_item(self, ticker: str, item: dict[str, Any]) -> dict[str, Any]:
        year = item.get("year")
        quarter_num = item.get("quarter")
        quarter_label = item.get("quarter_label")
        if not quarter_label and year and quarter_num:
            quarter_label = f"Q{quarter_num} {year}"
        return {
            "ticker": ticker.upper(),
            "date": item.get("date", ""),
            "quarter": quarter_label or quarter_num,
            "year": year,
            "content": (item.get("content") or "")[:8000],
        }

    def _fetch_stable_transcript(
        self,
        ticker: str,
        *,
        year: int,
        quarter: int,
    ) -> list[dict[str, Any]]:
        data = self._get_stable(
            "earning-call-transcript",
            {"symbol": ticker.upper(), "year": year, "quarter": quarter},
        )
        if isinstance(data, list):
            return [self._normalize_transcript_item(ticker, item) for item in data if item.get("content")]
        if isinstance(data, dict) and data.get("content"):
            return [self._normalize_transcript_item(ticker, data)]
        return []

    def _fetch_latest_stable_period(self, ticker: str) -> tuple[int | None, int | None]:
        data = self._get_stable("earning-call-transcript-dates", {"symbol": ticker.upper()})
        if not isinstance(data, list) or not data:
            return None, None
        latest = data[0]
        year = latest.get("fiscalYear") or latest.get("year")
        quarter = latest.get("quarter")
        try:
            return int(year), int(quarter)
        except (TypeError, ValueError):
            return None, None

    def _fetch_legacy_transcript(self, ticker: str, *, year: int, quarter: int) -> list[dict[str, Any]]:
        data = self._get(
            f"/earning_call_transcript/{ticker.upper()}",
            {"year": year, "quarter": quarter},
        )
        if isinstance(data, list):
            return [self._normalize_transcript_item(ticker, item) for item in data if item.get("content")]
        if isinstance(data, dict) and data.get("content"):
            return [self._normalize_transcript_item(ticker, data)]
        return []

    def fetch_earnings_call_transcripts(
        self,
        ticker: str,
        *,
        quarter: str | None = None,
        limit: int = 2,
    ) -> list[dict[str, Any]]:
        """Fetch recent earnings call transcripts for a ticker."""
        subscription_blocked = False
        subscription_detail = ""
        year, quarter_num = _parse_quarter_label(quarter)
        if year is None or quarter_num is None:
            try:
                year, quarter_num = self._fetch_latest_stable_period(ticker)
            except FMPSubscriptionError as exc:
                subscription_blocked = True
                subscription_detail = str(exc)
                year, quarter_num = None, None

        if year is None or quarter_num is None:
            if subscription_blocked:
                raise FMPSubscriptionError(subscription_detail or "FMP transcript endpoints restricted")
            return []

        try:
            stable = self._fetch_stable_transcript(ticker, year=year, quarter=quarter_num)
            if stable:
                return stable[:limit]
        except FMPSubscriptionError as exc:
            subscription_blocked = True
            subscription_detail = str(exc)

        try:
            legacy = self._fetch_legacy_transcript(ticker, year=year, quarter=quarter_num)
            if legacy:
                return legacy[:limit]
        except FMPSubscriptionError as exc:
            subscription_blocked = True
            subscription_detail = str(exc)

        if subscription_blocked:
            raise FMPSubscriptionError(subscription_detail or "FMP transcript endpoints restricted")
        return []

    def fetch_earnings_calendar(self, ticker: str) -> list[dict[str, Any]]:
        data = self._get("/historical/earning_calendar/" + ticker.upper())
        if isinstance(data, list):
            return data[:5]
        return []
