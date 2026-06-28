"""LangChain wrappers for legacy data retrieval and calculator tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import calculators, data_retrieval


@tool
def get_financial_statements(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Fetch bundled financial statements for a ticker."""
    return data_retrieval.get_financial_statements(ticker)


@tool
def get_consensus_estimates(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Fetch analyst consensus estimates for a ticker."""
    return data_retrieval.get_consensus_estimates(ticker)


@tool
def yfinance_consensus(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Alias for consensus estimates via yfinance/info sources."""
    return data_retrieval.get_consensus_estimates(ticker)


@tool
def get_current_price(ticker: Annotated[str, "Ticker symbol"]) -> str:
    """Get current price briefing for a ticker."""
    return data_retrieval.get_current_price(ticker)


@tool
def search_web(query: Annotated[str, "Search query"]) -> dict[str, Any]:
    """Legacy web search stub; prefer web_search."""
    return data_retrieval.search_web(query)


@tool
def search_company_filings(
    ticker: Annotated[str, "Ticker symbol"],
    query: Annotated[str, "Filing search query"] = "",
) -> str:
    """Search company fundamentals/filings metadata."""
    return data_retrieval.search_company_filings(ticker, query)


@tool
def get_news(ticker: Annotated[str, "Ticker symbol"]) -> str:
    """Fetch recent news for a ticker."""
    return data_retrieval.get_news(ticker)


@tool
def calculate_cagr(
    values: Annotated[list[float], "Numeric series values"],
    periods: Annotated[int, "Number of periods between first and last value"],
) -> dict:
    """Calculate compound annual growth rate."""
    return calculators.calculate_cagr(values, periods)


@tool
def calculate_total_return(
    price_upside_pct: Annotated[float, "Expected price upside percent"],
    dividend_yield_pct: Annotated[float, "Dividend yield percent"] = 0.0,
) -> dict:
    """Calculate expected total return percent."""
    return calculators.calculate_total_return(price_upside_pct, dividend_yield_pct)


@tool
def calculate_trading_multiple_valuation(
    ticker: Annotated[str, "Ticker symbol"],
    current_price: Annotated[float, "Current share price"],
    forecast_model: Annotated[dict | None, "Forecast model assumptions"] = None,
    facts: Annotated[list[dict], "Supporting valuation facts"] = None,
) -> dict:
    """Run trading multiple valuation mock calculation."""
    return calculators.calculate_trading_multiple_valuation(
        ticker, current_price, forecast_model, facts or []
    )


@tool
def calculate_sensitivity_table(
    base_target: Annotated[float, "Base target price"],
    scenarios: Annotated[list[dict], "Scenario definitions with target_multiplier"],
) -> list[dict]:
    """Build valuation sensitivity table for scenarios."""
    return calculators.calculate_sensitivity_table(base_target, scenarios)
