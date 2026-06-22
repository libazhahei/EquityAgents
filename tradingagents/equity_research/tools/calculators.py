"""Deterministic calculators for equity research."""

from __future__ import annotations

from tradingagents.equity_research.tools.interface import route_equity_tool


def calculate_cagr(values: list[float], periods: int) -> dict:
    return route_equity_tool("calculate_cagr", values, periods)


def calculate_total_return(price_upside_pct: float, dividend_yield_pct: float = 0.0) -> dict:
    return route_equity_tool(
        "calculate_total_return",
        price_upside_pct=price_upside_pct,
        dividend_yield_pct=dividend_yield_pct,
    )


def calculate_trading_multiple_valuation(
    ticker: str,
    current_price: float,
    forecast_model: dict | None,
    facts: list[dict],
) -> dict:
    return route_equity_tool(
        "calculate_trading_multiple_valuation",
        ticker,
        current_price,
        forecast_model,
        facts,
    )


def calculate_sensitivity_table(base_target: float, scenarios: list[dict]) -> list[dict]:
    return route_equity_tool("calculate_sensitivity_table", base_target, scenarios)
