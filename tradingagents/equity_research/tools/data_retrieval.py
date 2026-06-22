"""Data retrieval tools for equity research."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.equity_research.tools.interface import route_equity_tool


def get_financial_statements(ticker: Annotated[str, "ticker symbol"]) -> dict[str, Any]:
    return route_equity_tool("get_financial_statements", ticker)


def get_consensus_estimates(ticker: Annotated[str, "ticker symbol"]) -> dict[str, Any]:
    return route_equity_tool("get_consensus_estimates", ticker)


def get_current_price(ticker: Annotated[str, "ticker symbol"]) -> str:
    return route_equity_tool("get_current_price", ticker)


def search_web(query: Annotated[str, "search query"]) -> dict[str, Any]:
    """Perplexity search is invoked via dedicated search node; stub for skill permissions."""
    return {"query": query, "note": "use perplexity search node"}


def search_company_filings(
    ticker: Annotated[str, "ticker symbol"],
    query: Annotated[str, "filing search query"] = "",
) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return route_to_vendor("get_fundamentals", ticker, today)


def get_news(ticker: Annotated[str, "ticker symbol"]) -> str:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return route_to_vendor("get_news", ticker, today)
