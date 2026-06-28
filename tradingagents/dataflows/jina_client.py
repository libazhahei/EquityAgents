"""Jina Reader and Search API client."""

from __future__ import annotations

import os
from typing import Any

import httpx

from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorRateLimitError,
)


class JinaClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("JINA_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        self._ensure_configured()
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise VendorNotConfiguredError("JINA_API_KEY is not set")

    def fetch_url(self, url: str) -> dict[str, Any]:
        self._ensure_configured()
        reader_url = f"https://r.jina.ai/{url}"
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.get(reader_url, headers=self._headers())
                if response.status_code == 429:
                    raise VendorRateLimitError("Jina rate limit exceeded")
                response.raise_for_status()
                text = response.text
        except VendorRateLimitError:
            raise
        except VendorNotConfiguredError:
            raise
        except Exception as exc:
            raise NoMarketDataError(symbol=url, detail=str(exc)) from exc

        if not text.strip():
            raise NoMarketDataError(symbol=url, detail="empty Jina reader response")
        return {"url": url, "content": text}

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
    ) -> dict[str, Any]:
        self._ensure_configured()
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    "https://s.jina.ai/",
                    headers=self._headers(),
                    json={"q": query, "num": max_results},
                )
                if response.status_code == 429:
                    raise VendorRateLimitError("Jina rate limit exceeded")
                response.raise_for_status()
                data = response.json()
        except VendorRateLimitError:
            raise
        except VendorNotConfiguredError:
            raise
        except Exception as exc:
            raise NoMarketDataError(symbol=query, detail=str(exc)) from exc

        results = data.get("data") or data.get("results") or []
        if not results:
            raise NoMarketDataError(symbol=query, detail="no Jina search results")

        normalized = []
        for item in results[:max_results]:
            if isinstance(item, dict):
                normalized.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", item.get("description", "")),
                })
            else:
                normalized.append({"title": str(item), "url": "", "content": ""})

        return {"query": query, "results": normalized}
