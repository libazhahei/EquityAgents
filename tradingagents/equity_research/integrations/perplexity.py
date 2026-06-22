"""Perplexity Search API integration."""

from __future__ import annotations

import logging
import os
from enum import Enum
from typing import Any

import httpx

from tradingagents.equity_research.integrations.redis_cache import RedisClient

logger = logging.getLogger(__name__)

PERPLEXITY_SEARCH_URL = "https://api.perplexity.ai/search"
PERPLEXITY_CHAT_URL = "https://api.perplexity.ai/chat/completions"


class SearchMode(str, Enum):
    EXPLORATORY = "exploratory"
    TARGETED = "targeted"
    CONTRADICTION = "contradiction"


_SYSTEM_PROMPTS = {
    SearchMode.EXPLORATORY: (
        "You are an equity research assistant. Provide factual, cited information "
        "about companies and industries. Focus on publicly verifiable facts."
    ),
    SearchMode.TARGETED: (
        "You are an evidence retrieval assistant. Find specific, citable evidence "
        "that supports or refutes an investment hypothesis. Cite primary sources."
    ),
    SearchMode.CONTRADICTION: (
        "You are a devil's advocate researcher. Find counter-evidence, risks, and "
        "bear cases for the given thesis. Cite credible sources."
    ),
}


class PerplexityClient:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.api_key = (
            self.config.get("perplexity_api_key")
            or os.environ.get("PERPLEXITY_API_KEY", "")
        )
        self.redis = RedisClient(config)
        self.max_calls_per_minute = int(
            self.config.get("equity_research", {}).get("perplexity_rate_limit", 20)
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.EXPLORATORY,
        *,
        max_results: int = 5,
    ) -> dict[str, Any]:
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not set; returning empty search result")
            return {"answer": "", "citations": [], "query": query, "mode": mode.value}

        if not self.redis.rate_limit("perplexity", self.max_calls_per_minute):
            logger.warning("Perplexity rate limit exceeded")
            return {"answer": "", "citations": [], "query": query, "mode": mode.value, "rate_limited": True}

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    PERPLEXITY_SEARCH_URL,
                    headers=self._headers(),
                    json={"query": query, "max_results": max_results},
                )
                response.raise_for_status()
                data = response.json()
                results = data.get("results", [])
                citations = [r.get("url", "") for r in results if r.get("url")]
                snippets = [r.get("snippet", r.get("title", "")) for r in results]
                answer = "\n\n".join(s for s in snippets if s)
                return {
                    "answer": answer,
                    "citations": citations,
                    "query": query,
                    "mode": mode.value,
                    "raw_results": results,
                }
        except Exception as exc:
            logger.warning("Perplexity search failed: %s", exc)
            return self._chat_fallback(query, mode)

    def _chat_fallback(self, query: str, mode: SearchMode) -> dict[str, Any]:
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    PERPLEXITY_CHAT_URL,
                    headers=self._headers(),
                    json={
                        "model": "sonar-pro",
                        "messages": [
                            {"role": "system", "content": _SYSTEM_PROMPTS[mode]},
                            {"role": "user", "content": query},
                        ],
                    },
                )
                response.raise_for_status()
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                citations = data.get("citations", [])
                return {
                    "answer": content,
                    "citations": citations,
                    "query": query,
                    "mode": mode.value,
                }
        except Exception as exc:
            logger.warning("Perplexity chat fallback failed: %s", exc)
            return {"answer": "", "citations": [], "query": query, "mode": mode.value, "error": str(exc)}

    def finance_verify(self, ticker: str, claim: str) -> dict[str, Any]:
        """Optional Finance Search verification — used only for IC quality check."""
        query = f"Verify this financial claim about {ticker}: {claim}"
        return self.search(query, mode=SearchMode.TARGETED, max_results=3)


def generate_search_plan(
    ticker: str,
    hypothesis: dict[str, Any],
    mode: SearchMode,
    max_queries: int,
) -> list[dict[str, str]]:
    hid = hypothesis.get("hypothesis_id", "")
    if mode == SearchMode.EXPLORATORY:
        queries = [
            f"{ticker} business model key revenue drivers",
            f"{ticker} industry competitive landscape market share",
            f"{ticker} recent earnings management guidance",
        ]
    elif mode == SearchMode.TARGETED:
        queries = [f"{ticker} {et}" for et in hypothesis.get("required_evidence", [])]
        if not queries:
            queries = [f"{ticker} {hypothesis.get('statement', '')}"]
    else:
        queries = [
            f"{ticker} challenges risks downside",
            f"{ticker} competitive threat bear case",
        ]
    return [
        {"query": q, "hypothesis_id": hid, "mode": mode.value}
        for q in queries[:max_queries]
    ]
