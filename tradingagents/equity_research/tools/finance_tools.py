"""Finance tools for equity research."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.tools.interface import route_equity_tool


def stock_quote(ticker: str) -> dict[str, Any]:
    return route_equity_tool("stock_quote", ticker)


def company_profile(ticker: str) -> dict[str, Any]:
    return route_equity_tool("company_profile", ticker)


def financial_statement_fetch(ticker: str, period: str = "annual") -> dict[str, Any]:
    return route_equity_tool("financial_statement_fetch", ticker, period=period)


def earnings_calendar(ticker: str) -> Any:
    return route_equity_tool("earnings_calendar", ticker)


def analyst_estimates_fetch(ticker: str) -> dict[str, Any]:
    return route_equity_tool("analyst_estimates_fetch", ticker)


def transcript_search(ticker: str, quarter: str | None = None) -> Any:
    return route_equity_tool("transcript_search", ticker, quarter=quarter)


def filings_search(ticker: str, form_type: str | None = None) -> Any:
    return route_equity_tool("filings_search", ticker, form_type=form_type)


def filing_reader(filing_url: str | None = None, filing_id: str | None = None) -> dict[str, Any]:
    return route_equity_tool("filing_reader", filing_url=filing_url, filing_id=filing_id)


def peer_comps_fetch(ticker: str) -> dict[str, Any]:
    return route_equity_tool("peer_comps_fetch", ticker)


def valuation_multiples_fetch(tickers: str | list[str]) -> Any:
    return route_equity_tool("valuation_multiples_fetch", tickers)
