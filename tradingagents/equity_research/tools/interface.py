"""Equity research tool vendor routing and catalog."""

from __future__ import annotations

from typing import Any, Callable

from tradingagents.dataflows import equity_vendors
from tradingagents.dataflows.config import get_config
from tradingagents.dataflows.vendor_routing import (
    DEFAULT_VENDOR_ORDER,
    build_vendor_chain,
    execute_vendor_chain,
)
from tradingagents.equity_research.computation.valuation_mock import compute_valuation_mock
from tradingagents.equity_research.tools.tool_catalog import (
    EQUITY_TOOLS_CATEGORIES,
    get_category_for_tool,
)

# Register default vendor order for equity tools
DEFAULT_VENDOR_ORDER.update({
    "web_search": ["tavily", "jina"],
    "web_fetch": ["jina", "tavily"],
    "news_search": ["tavily", "jina"],
    "stock_quote": ["yfinance", "alpha_vantage"],
    "company_profile": ["yfinance", "fmp"],
    "financial_statement_fetch": ["yfinance", "alpha_vantage"],
    "earnings_calendar": ["fmp", "yfinance"],
    "analyst_estimates_fetch": ["fmp", "info_sources", "yfinance"],
    "transcript_search": ["alpha_vantage", "fmp", "perplexity"],
    "filings_search": ["edgar"],
    "filing_reader": ["edgar"],
    "peer_comps_fetch": ["yfinance", "fmp"],
    "valuation_multiples_fetch": ["yfinance", "fmp"],
})

WRAP_VENDOR_METADATA = {
    "web_search", "web_fetch", "news_search",
    "stock_quote", "company_profile", "financial_statement_fetch",
    "earnings_calendar", "analyst_estimates_fetch", "transcript_search",
    "filings_search", "filing_reader", "peer_comps_fetch", "valuation_multiples_fetch",
}

EQUITY_METHOD_CATEGORIES: dict[str, str] = {
    "web_search": "web_search_data",
    "web_fetch": "web_fetch_data",
    "news_search": "web_search_data",
    "stock_quote": "equity_finance",
    "company_profile": "equity_finance",
    "financial_statement_fetch": "equity_finance",
    "earnings_calendar": "equity_finance",
    "analyst_estimates_fetch": "equity_finance",
    "peer_comps_fetch": "equity_finance",
    "valuation_multiples_fetch": "equity_finance",
    "transcript_search": "transcripts_data",
    "filings_search": "filings_data",
    "filing_reader": "filings_data",
}

EQUITY_VENDOR_METHODS: dict[str, dict[str, Callable[..., Any]]] = {
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
    "web_search": {
        "tavily": equity_vendors.web_search_tavily,
        "jina": equity_vendors.web_search_jina,
    },
    "web_fetch": {
        "jina": equity_vendors.web_fetch_jina,
        "tavily": equity_vendors.web_fetch_tavily,
    },
    "news_search": {
        "tavily": equity_vendors.news_search_tavily,
        "jina": equity_vendors.news_search_jina,
    },
    "stock_quote": {
        "yfinance": equity_vendors.stock_quote_yfinance,
        "alpha_vantage": equity_vendors.stock_quote_alpha_vantage,
    },
    "company_profile": {
        "yfinance": equity_vendors.company_profile_yfinance,
        "fmp": equity_vendors.company_profile_fmp,
    },
    "financial_statement_fetch": {
        "yfinance": equity_vendors.financial_statement_fetch_yfinance,
        "alpha_vantage": equity_vendors.financial_statement_fetch_alpha_vantage,
    },
    "earnings_calendar": {
        "fmp": equity_vendors.earnings_calendar_fmp,
        "yfinance": equity_vendors.earnings_calendar_yfinance,
    },
    "analyst_estimates_fetch": {
        "fmp": equity_vendors.analyst_estimates_fetch_fmp,
        "info_sources": equity_vendors.analyst_estimates_fetch_info_sources,
        "yfinance": equity_vendors.analyst_estimates_fetch_yfinance,
    },
    "transcript_search": {
        "alpha_vantage": equity_vendors.transcript_search_alpha_vantage,
        "fmp": equity_vendors.transcript_search_fmp,
        "perplexity": equity_vendors.transcript_search_perplexity,
    },
    "filings_search": {
        "edgar": equity_vendors.filings_search_edgar,
    },
    "filing_reader": {
        "edgar": equity_vendors.filing_reader_edgar,
    },
    "peer_comps_fetch": {
        "yfinance": equity_vendors.peer_comps_fetch_yfinance,
        "fmp": equity_vendors.peer_comps_fetch_fmp,
    },
    "valuation_multiples_fetch": {
        "yfinance": equity_vendors.valuation_multiples_fetch_yfinance,
        "fmp": equity_vendors.valuation_multiples_fetch_fmp,
    },
}


def route_equity_tool(method: str, *args, **kwargs) -> Any:
    if method not in EQUITY_VENDOR_METHODS:
        raise ValueError(f"Equity tool '{method}' not supported")
    category = EQUITY_METHOD_CATEGORIES.get(method) or get_category_for_tool(method)
    config = get_config()

    transcript_ticker = ""
    if method == "transcript_search":
        from tradingagents.equity_research.integrations.transcript_cache import (
            get_cached_transcript_search,
            set_cached_transcript_search,
        )

        transcript_ticker = str(args[0] if args else kwargs.get("ticker", ""))
        cached = get_cached_transcript_search(
            config,
            transcript_ticker,
            quarter=kwargs.get("quarter"),
            query=kwargs.get("query"),
        )
        if cached is not None:
            return cached

    vendor_chain = build_vendor_chain(
        method,
        EQUITY_VENDOR_METHODS[method],
        category=category,
        config=config,
        equity_override=True,
    )
    wrap = method in WRAP_VENDOR_METADATA
    result = execute_vendor_chain(
        method,
        vendor_chain,
        EQUITY_VENDOR_METHODS[method],
        *args,
        wrap_metadata=wrap,
        no_data_as_string=False,
        **kwargs,
    )
    if not wrap:
        return result
    if isinstance(result, dict) and "vendor_used" in result:
        wrapped = result
    elif isinstance(result, dict):
        wrapped = {
            **result,
            "vendor_used": vendor_chain[0] if vendor_chain else None,
            "fallback_attempted": vendor_chain,
        }
    else:
        wrapped = {
            "data": result,
            "vendor_used": vendor_chain[0] if vendor_chain else None,
            "fallback_attempted": vendor_chain,
        }

    if method == "transcript_search":
        set_cached_transcript_search(
            config,
            transcript_ticker,
            quarter=kwargs.get("quarter"),
            query=kwargs.get("query"),
            result=wrapped,
        )
    return wrapped


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


__all__ = ["EQUITY_TOOLS_CATEGORIES", "EQUITY_VENDOR_METHODS", "route_equity_tool"]
