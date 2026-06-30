"""LangChain tools for section planner grounding."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import search_tools

_MAX_QUERIES = 5
_MAX_RESULTS_PER_QUERY = 3


@tool
def batch_light_grounding_search(
    queries: Annotated[list[str], "Up to 5 lightweight web search queries"],
    max_results_per_query: Annotated[int, "Max result snippets per query"] = _MAX_RESULTS_PER_QUERY,
) -> dict[str, Any]:
    """Run lightweight web searches for section planner grounding only (not full research)."""
    snippets: list[dict[str, Any]] = []
    api_calls = 0
    errors: list[str] = []

    for query in (queries or [])[:_MAX_QUERIES]:
        try:
            result = search_tools.web_search(query)
            api_calls += 1
            items = result.get("results") or result.get("items") or []
            if isinstance(items, dict):
                items = list(items.values())
            formatted = []
            for item in items[:max_results_per_query]:
                if isinstance(item, dict):
                    title = item.get("title", "")
                    content = item.get("content") or item.get("snippet") or item.get("text", "")
                    url = item.get("url", "")
                    formatted.append(f"- {title}: {content[:300]} ({url})".strip())
                else:
                    formatted.append(str(item)[:300])
            snippets.append({"query": query, "results": formatted})
        except Exception as exc:
            errors.append(f"{query}: {exc}")
            snippets.append({"query": query, "results": [], "error": str(exc)})

    return {
        "snippets": snippets,
        "api_calls": api_calls,
        "errors": errors,
    }
