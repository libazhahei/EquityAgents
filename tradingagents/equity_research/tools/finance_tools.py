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


def transcript_search(ticker: str, quarter: str | None = None, query: str | None = None) -> Any:
    return route_equity_tool("transcript_search", ticker, quarter=quarter, query=query)


def filings_search(
    ticker: str,
    keywords: str,
    form_type: str | None = None,
    section: str | None = None,
    top_k: int = 8,
    max_chars: int = 8000,
    dedupe: bool = True,
    rerank: bool = True,
    prefer_recent: bool | None = None,
    max_per_group: int = 2,
) -> Any:
    """Static stub — use make_filings_search_tool(deps) in executor."""
    return route_equity_tool(
        "filings_search",
        ticker,
        keywords=keywords,
        form_type=form_type,
        section=section,
        top_k=top_k,
        max_chars=max_chars,
        dedupe=dedupe,
        rerank=rerank,
        prefer_recent=prefer_recent,
        max_per_group=max_per_group,
    )


def filing_reader(
    filing_url: str | None = None,
    filing_id: str | None = None,
    section: str | None = None,
    ticker: str | None = None,
    year: int | None = None,
    quarter: str | None = None,
    chunk_index: int | None = None,
    table_index: int | None = None,
) -> dict[str, Any]:
    return route_equity_tool(
        "filing_reader",
        filing_url=filing_url,
        filing_id=filing_id,
        section=section,
        ticker=ticker,
        year=year,
        quarter=quarter,
        chunk_index=chunk_index,
        table_index=table_index,
    )


def peer_comps_fetch(ticker: str) -> dict[str, Any]:
    return route_equity_tool("peer_comps_fetch", ticker)


def valuation_multiples_fetch(tickers: str | list[str]) -> Any:
    return route_equity_tool("valuation_multiples_fetch", tickers)
