"""Default queries and normalization for consensus task."""

from __future__ import annotations

from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    QueryItem,
    QueryPlan,
    SearchMode,
)


def default_queries(ticker: str) -> list[QueryItem]:
    return [
        QueryItem(
            query=f"{ticker} public analyst consensus revenue EPS estimates range earnings calls news aggregator",
            target_dimension="quantitative_estimates",
            mode=SearchMode.TARGETED,
            priority=5,
        ),
        QueryItem(
            query=f"{ticker} key metrics analysts watch most important KPIs earnings call",
            target_dimension="kpi_focus",
            mode=SearchMode.EXPLORATORY,
            priority=4,
        ),
        QueryItem(
            query=f"{ticker} forward PE EV EBITDA multiple implied growth vs peers",
            target_dimension="pricing_assumptions",
            mode=SearchMode.TARGETED,
            priority=3,
        ),
        QueryItem(
            query=f"{ticker} bull case bear case investment thesis debate",
            target_dimension="narrative_framework",
            mode=SearchMode.EXPLORATORY,
            priority=2,
        ),
        QueryItem(
            query=f"{ticker} estimate revision after earnings guidance change recent",
            target_dimension="recent_delta",
            mode=SearchMode.TARGETED,
            priority=1,
        ),
    ]


def normalize_query_items(
    items: list[QueryItem],
    ticker: str,
    use_default_if_empty: bool,
) -> list[QueryItem]:
    normalized: list[QueryItem] = []
    for item in items:
        dim = item.target_dimension
        if dim not in CONSENSUS_DIMENSIONS:
            dim = "narrative_framework"
        normalized.append(
            QueryItem(
                query=str(item.query),
                target_dimension=dim,
                mode=item.mode,
                priority=item.priority,
            )
        )
    if normalized:
        return normalized
    return default_queries(ticker) if use_default_if_empty else []


def fallback_initial_plan(state: dict) -> QueryPlan:
    return QueryPlan(queries=default_queries(state.get("ticker", "")))
