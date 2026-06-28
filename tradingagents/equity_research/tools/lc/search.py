"""LangChain search tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import search_tools


@tool
def web_search(
    query: Annotated[str, "Search query"],
    recency: Annotated[str | None, "Recency window: day, week, month, or year"] = None,
) -> dict[str, Any]:
    """Run a general web search (Tavily/Jina with vendor fallback)."""
    return search_tools.web_search(query, recency=recency)


@tool
def web_fetch(url: Annotated[str, "URL to fetch as markdown/text"]) -> dict[str, Any]:
    """Fetch readable content from a URL."""
    return search_tools.web_fetch(url)


@tool
def news_search(
    query: Annotated[str, "News search query"],
    date_range: Annotated[str | None, "Optional date range filter, e.g. week or 2024-01-01:2024-06-01"] = None,
) -> dict[str, Any]:
    """Search recent news and events."""
    return search_tools.news_search(query, date_range=date_range)


@tool
def source_quality_check(url: Annotated[str, "Source URL to score"]) -> dict[str, Any]:
    """Score the reliability of a web source URL."""
    return search_tools.source_quality_check(url)


@tool
def citation_extractor(text: Annotated[str, "Text containing citations"]) -> dict[str, Any]:
    """Extract citation URLs from text."""
    return search_tools.citation_extractor(text)


@tool
def search_deduper(
    results: Annotated[list[dict], "Search result items with title/url fields"],
) -> dict[str, Any]:
    """Deduplicate similar search results."""
    return search_tools.search_deduper(results)
