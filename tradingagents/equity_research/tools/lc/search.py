"""LangChain search tools."""

from __future__ import annotations

import json
from typing import Annotated, Any, Callable

from langchain_core.tools import BaseTool, tool

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


def make_batch_perplexity_search_tool(
    deps: Any,
    *,
    search_fn: Callable[..., Any] | None = None,
) -> BaseTool:
    @tool
    def batch_perplexity_search(
        ticker: Annotated[str, "Ticker symbol"],
        queries: Annotated[
            str | list[str | dict[str, Any]],
            "One query string, one query item dict, or a list of query items",
        ],
        iteration: Annotated[int, "Research iteration index"] = 0,
        search_memory: Annotated[
            list[dict] | None,
            "Prior search records for exact-query cache reuse",
        ] = None,
    ) -> str:
        """Run one or many Perplexity searches with batch dedup and memory cache."""
        result = search_tools.batch_perplexity_search(
            deps,
            ticker=ticker,
            queries=queries,
            iteration=iteration,
            search_memory=search_memory,
            search_fn=search_fn,
        )
        return json.dumps(result)

    return batch_perplexity_search
