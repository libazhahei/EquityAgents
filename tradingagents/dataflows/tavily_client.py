"""Tavily search API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)


class TavilyClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("TAVILY_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise VendorNotConfiguredError("TAVILY_API_KEY is not set")

    def search(
        self,
        query: str,
        *,
        recency: str | None = None,
        topic: str = "general",
        max_results: int = 5,
    ) -> dict[str, Any]:
        self._ensure_configured()
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "query": query,
            "max_results": max_results,
            "topic": topic,
        }
        if recency:
            payload["days"] = _recency_to_days(recency)

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post("https://api.tavily.com/search", json=payload)
                if response.status_code == 429:
                    raise VendorRateLimitError("Tavily rate limit exceeded")
                response.raise_for_status()
                data = response.json()
        except VendorRateLimitError:
            raise
        except VendorNotConfiguredError:
            raise
        except Exception as exc:
            raise NoMarketDataError(symbol=query, detail=str(exc)) from exc

        results = data.get("results") or []
        if not results and not data.get("answer"):
            raise NoMarketDataError(symbol=query, detail="no Tavily results")

        return {
            "query": query,
            "answer": data.get("answer", ""),
            "results": [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("content", ""),
                    "score": r.get("score"),
                }
                for r in results
            ],
        }

    def extract(self, url: str) -> dict[str, Any]:
        self._ensure_configured()
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    "https://api.tavily.com/extract",
                    json={"api_key": self.api_key, "urls": [url]},
                )
                if response.status_code == 429:
                    raise VendorRateLimitError("Tavily rate limit exceeded")
                response.raise_for_status()
                data = response.json()
        except VendorRateLimitError:
            raise
        except VendorNotConfiguredError:
            raise
        except Exception as exc:
            raise NoMarketDataError(symbol=url, detail=str(exc)) from exc

        results = data.get("results") or []
        if not results:
            raise NoMarketDataError(symbol=url, detail="no Tavily extract content")
        first = results[0]
        return {"url": url, "content": first.get("raw_content") or first.get("content", "")}


def _recency_to_days(recency: str) -> int:
    mapping = {"day": 1, "week": 7, "month": 30, "year": 365}
    return mapping.get(recency.lower(), 7)
