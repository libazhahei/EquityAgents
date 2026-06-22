"""Equity research tool vendor routing."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from tradingagents.dataflows.interface import route_to_vendor
from tradingagents.equity_research.computation.valuation_mock import compute_valuation_mock
from tradingagents.equity_research.integrations.info_sources import default_registry

EQUITY_VENDOR_METHODS: dict[str, dict[str, Callable[..., Any]]] = {
    "get_financial_statements": {
        "yfinance": lambda ticker, **_: _yfinance_financials(ticker),
        "info_sources": lambda ticker, **_: _info_sources_financials(ticker),
    },
    "get_consensus_estimates": {
        "info_sources": lambda ticker, **_: _info_sources_consensus(ticker),
        "yfinance": lambda ticker, **_: _yfinance_consensus(ticker),
    },
    "get_current_price": {
        "yfinance": lambda ticker, **_: route_to_vendor(
            "get_briefing_stock_info", ticker, datetime.utcnow().strftime("%Y-%m-%d")
        ),
    },
    "calculate_trading_multiple_valuation": {
        "internal": lambda ticker, current_price, forecast_model, facts, **_: compute_valuation_mock(
            ticker, float(current_price or 0), forecast_model, facts
        ).model_dump(),
    },
    "calculate_cagr": {
        "internal": lambda values, periods, **_: _calculate_cagr(values, periods),
    },
    "calculate_total_return": {
        "internal": lambda price_upside_pct, dividend_yield_pct=0.0, **_: {
            "expected_total_return_pct": float(price_upside_pct) + float(dividend_yield_pct),
        },
    },
    "calculate_sensitivity_table": {
        "internal": lambda base_target, scenarios, **_: _calculate_sensitivity(base_target, scenarios),
    },
}


def route_equity_tool(method: str, *args, **kwargs) -> Any:
    if method not in EQUITY_VENDOR_METHODS:
        raise ValueError(f"Equity tool '{method}' not supported")
    vendors = EQUITY_VENDOR_METHODS[method]
    last_error: Exception | None = None
    for vendor, impl in vendors.items():
        try:
            return impl(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    raise RuntimeError(f"No vendor available for equity tool '{method}'")


def _yfinance_financials(ticker: str) -> dict[str, Any]:
    today = datetime.utcnow().strftime("%Y-%m-%d")
    return {
        "fundamentals": route_to_vendor("get_fundamentals", ticker, today),
        "income_statement": route_to_vendor("get_income_statement", ticker, "annual", today),
        "balance_sheet": route_to_vendor("get_balance_sheet", ticker, "annual", today),
        "cashflow": route_to_vendor("get_cashflow", ticker, "annual", today),
    }


def _info_sources_financials(ticker: str) -> dict[str, Any]:
    results = default_registry().fetch_all(ticker, "fundamentals")
    return results[0] if results else {}


def _info_sources_consensus(ticker: str) -> dict[str, Any]:
    results = default_registry().fetch_all(ticker, "consensus")
    return results[0] if results else {}


def _yfinance_consensus(ticker: str) -> dict[str, Any]:
    return _info_sources_consensus(ticker)


def _calculate_cagr(values: list[float], periods: int) -> dict[str, float]:
    if not values or periods <= 0 or values[0] == 0:
        return {"cagr": 0.0}
    cagr = (values[-1] / values[0]) ** (1 / periods) - 1
    return {"cagr": round(cagr, 4)}


def _calculate_sensitivity(base_target: float, scenarios: list[dict]) -> list[dict]:
    rows = []
    for scenario in scenarios:
        multiplier = float(scenario.get("target_multiplier", 1.0))
        rows.append(
            {
                "scenario": scenario.get("name", "scenario"),
                "assumptions": scenario.get("assumptions", ""),
                "implied_target_price": round(base_target * multiplier, 2),
            }
        )
    return rows
