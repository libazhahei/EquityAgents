"""Search tools for equity research."""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse

from tradingagents.equity_research.tools.interface import route_equity_tool

_TRUSTED_DOMAINS = {
    "sec.gov", "reuters.com", "bloomberg.com", "ft.com", "wsj.com",
    "cnbc.com", "finance.yahoo.com", "marketwatch.com",
}


def web_search(query: str, recency: str | None = None) -> dict[str, Any]:
    return route_equity_tool("web_search", query, recency=recency)


def web_fetch(url: str) -> dict[str, Any]:
    return route_equity_tool("web_fetch", url)


def news_search(query: str, date_range: str | None = None) -> dict[str, Any]:
    return route_equity_tool("news_search", query, date_range=date_range)


def source_quality_check(url: str) -> dict[str, Any]:
    parsed = urlparse(url)
    domain = (parsed.netloc or "").lower().removeprefix("www.")
    score = 0.5
    if domain in _TRUSTED_DOMAINS:
        score = 0.9
    elif domain.endswith(".gov") or domain.endswith(".edu"):
        score = 0.85
    elif not domain:
        score = 0.1
    return {"url": url, "domain": domain, "quality_score": score}


def citation_extractor(text: str) -> dict[str, Any]:
    urls = re.findall(r"https?://[^\s\)\]\"']+", text)
    return {"citations": list(dict.fromkeys(urls))}


def search_deduper(results: list[dict]) -> dict[str, Any]:
    deduped: list[dict] = []
    seen_titles: list[str] = []
    for item in results:
        title = (item.get("title") or item.get("url") or "").strip().lower()
        if not title:
            deduped.append(item)
            continue
        if any(
            SequenceMatcher(None, title, s).ratio() > 0.75 or title in s or s in title
            for s in seen_titles
        ):
            continue
        seen_titles.append(title)
        deduped.append(item)
    return {"results": deduped, "removed": len(results) - len(deduped)}
