"""LangChain finance tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import finance_tools


@tool
def stock_quote(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Get stock quote, price, and market data."""
    return finance_tools.stock_quote(ticker)


@tool
def company_profile(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Get company profile and business description."""
    return finance_tools.company_profile(ticker)


@tool
def financial_statement_fetch(
    ticker: Annotated[str, "Ticker symbol"],
    period: Annotated[str, "annual or quarterly"] = "annual",
) -> dict[str, Any]:
    """Fetch income statement, balance sheet, and cash flow."""
    return finance_tools.financial_statement_fetch(ticker, period=period)


@tool
def earnings_calendar(ticker: Annotated[str, "Ticker symbol"]) -> Any:
    """Get upcoming and recent earnings dates."""
    return finance_tools.earnings_calendar(ticker)


@tool
def analyst_estimates_fetch(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Fetch analyst consensus estimates."""
    return finance_tools.analyst_estimates_fetch(ticker)


@tool
def transcript_search(
    ticker: Annotated[str, "Ticker symbol"],
    quarter: Annotated[str | None, "Fiscal quarter label, e.g. Q1 2024"] = None,
) -> Any:
    """Search earnings call transcripts."""
    return finance_tools.transcript_search(ticker, quarter=quarter)


@tool
def filings_search(
    ticker: Annotated[str, "Ticker symbol"],
    form_type: Annotated[str | None, "SEC form type, e.g. 10-K, 10-Q, 8-K"] = None,
) -> Any:
    """Search recent SEC filings."""
    return finance_tools.filings_search(ticker, form_type=form_type)


@tool
def filing_reader(
    filing_url: Annotated[str | None, "Filing URL"] = None,
    filing_id: Annotated[str | None, "Filing id or URL alias"] = None,
) -> dict[str, Any]:
    """Read filing content from URL."""
    return finance_tools.filing_reader(filing_url=filing_url, filing_id=filing_id)


@tool
def peer_comps_fetch(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Fetch comparable peer companies."""
    return finance_tools.peer_comps_fetch(ticker)


@tool
def valuation_multiples_fetch(
    tickers: Annotated[str | list[str], "One ticker or comma-separated tickers"],
) -> Any:
    """Fetch valuation multiples for tickers."""
    return finance_tools.valuation_multiples_fetch(tickers)
