"""Default queries and normalization for assumption task."""

from __future__ import annotations

from tradingagents.equity_research.state.consensus_schemas import QueryItem, QueryPlan, SearchMode
from tradingagents.equity_research.tasks.assumption.schemas import ASSUMPTION_DIMENSIONS
from tradingagents.equity_research.tasks.consensus.compliance import append_compliance_suffix


def default_queries(ticker: str) -> list[QueryItem]:
    specs = [
        ("business_model", f"{ticker} how does the company make money revenue model margins"),
        ("market_sentiment", f"{ticker} market sentiment bull bear analyst rating consensus"),
        ("key_metrics", f"{ticker} key KPI metrics investors watch earnings focus"),
        ("debates", f"{ticker} key investment debates bull bear variant view"),
        ("stress_test", f"{ticker} consensus assumptions stress test risks"),
    ]
    items: list[QueryItem] = []
    for idx, (dim, query) in enumerate(specs):
        items.append(
            QueryItem(
                query=append_compliance_suffix(query),
                target_dimension=dim,
                mode=SearchMode.EXPLORATORY,
                priority=len(specs) - idx,
            )
        )
    return items


def normalize_query_items(
    items: list[QueryItem],
    ticker: str,
    use_default_if_empty: bool,
) -> list[QueryItem]:
    normalized: list[QueryItem] = []
    for item in items:
        dim = item.target_dimension
        if dim not in ASSUMPTION_DIMENSIONS:
            dim = "debates"
        normalized.append(
            QueryItem(
                query=append_compliance_suffix(str(item.query)),
                target_dimension=dim,
                mode=item.mode,
                priority=item.priority,
            )
        )
    if normalized:
        return normalized[:5]
    return default_queries(ticker) if use_default_if_empty else []


def fallback_initial_plan(state: dict) -> QueryPlan:
    return QueryPlan(queries=default_queries(state.get("ticker", "")))
