"""Perplexity search tool for the consensus subgraph."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.runtime.utils.domain_denylist import (
    denylists_to_api_filter,
    filter_citation_urls,
    resolve_search_domain_denylist,
)
from tradingagents.equity_research.state.consensus_schemas import EvidenceItem
from tradingagents.llm_clients.perplexity_client import SearchMode as PerplexitySearchMode


DIMENSION_MODE_MAP: dict[str, PerplexitySearchMode] = {
    "quantitative_estimates": PerplexitySearchMode.TARGETED,
    "kpi_focus": PerplexitySearchMode.EXPLORATORY,
    "pricing_assumptions": PerplexitySearchMode.TARGETED,
    "narrative_framework": PerplexitySearchMode.EXPLORATORY,
    "recent_delta": PerplexitySearchMode.TARGETED,
}


def resolve_search_mode(target_dimension: str, mode: str | None = None) -> PerplexitySearchMode:
    if mode:
        try:
            return PerplexitySearchMode(mode.lower())
        except ValueError:
            pass
    return DIMENSION_MODE_MAP.get(target_dimension, PerplexitySearchMode.EXPLORATORY)


def execute_perplexity_search(
    deps: Any,
    *,
    query: str,
    mode: str | PerplexitySearchMode,
    target_dimension: str,
    ticker: str,
) -> EvidenceItem:
    """Run Perplexity search and register citations as documents."""
    if isinstance(mode, str):
        search_mode = resolve_search_mode(target_dimension, mode)
    else:
        search_mode = mode

    answer = ""
    citations: list[str] = []
    doc_ids: list[str] = []

    denylist = resolve_search_domain_denylist(getattr(deps, "config", None))
    api_filter = denylists_to_api_filter(denylist) if denylist else None

    if deps.perplexity and getattr(deps.perplexity, "api_key", None):
        result = deps.perplexity.search(
            query,
            mode=search_mode,
            search_domain_filter=api_filter,
        )
        answer = result.get("answer", "")
        citations = filter_citation_urls(list(result.get("citations", [])), denylist)
        for url in citations:
            doc = deps.documents.register(
                ticker=ticker,
                source_type="news",
                title=url,
                source_url=url,
            )
            doc_ids.append(doc["doc_id"])

    return EvidenceItem(
        answer=answer,
        citations=citations,
        target_dimension=target_dimension,
        query_used=query,
        retrieved_at=datetime.utcnow().isoformat(),
        doc_ids=doc_ids,
    )


def make_perplexity_search_tool(deps: Any):
    @tool
    def perplexity_search(
        ticker: Annotated[str, "Ticker symbol"],
        query: Annotated[str, "Search query (10-80 English words)"],
        target_dimension: Annotated[
            str,
            "One of: quantitative_estimates, kpi_focus, pricing_assumptions, "
            "narrative_framework, recent_delta",
        ],
        mode: Annotated[str, "exploratory or targeted"] = "exploratory",
    ) -> str:
        """Run Perplexity web search for equity research evidence."""
        evidence = execute_perplexity_search(
            deps,
            query=query,
            mode=mode,
            target_dimension=target_dimension,
            ticker=ticker,
        )
        return json.dumps(evidence.model_dump())

    return perplexity_search
