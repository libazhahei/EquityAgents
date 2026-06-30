"""Default queries and normalization for assumption task."""

from __future__ import annotations

from tradingagents.equity_research.state.consensus_schemas import QueryItem, QueryPlan, SearchMode
from tradingagents.equity_research.tasks.assumption.schemas import ASSUMPTION_SEARCH_DIMENSIONS
from tradingagents.equity_research.tasks.consensus.compliance import append_compliance_suffix


def default_queries(ticker: str) -> list[QueryItem]:
    specs = [
        (
            "demand_assumptions",
            f"{ticker} end-market demand durability customer spending plans backlog order visibility",
        ),
        (
            "product_ramp_assumptions",
            f"{ticker} product ramp timing transition risk shipment cadence supply constraints",
        ),
        (
            "margin_assumptions",
            f"{ticker} gross margin bridge product mix pricing power ramp costs",
        ),
        (
            "competition_assumptions",
            f"{ticker} market share custom silicon risk alternative suppliers pricing pressure",
        ),
        (
            "falsification_tests",
            f"{ticker} downside scenario key assumption failure leading indicators early warning",
        ),
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
        if dim not in ASSUMPTION_SEARCH_DIMENSIONS:
            dim = "demand_assumptions"
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
