"""Thin vendor wrappers delegating to integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import yfinance as yf

from tradingagents.dataflows.errors import NoMarketDataError, VendorNotConfiguredError
from tradingagents.dataflows.jina_client import JinaClient
from tradingagents.dataflows.tavily_client import TavilyClient


def web_search_tavily(query: str, recency: str | None = None, **_: Any) -> dict[str, Any]:
    return TavilyClient().search(query, recency=recency)


def web_search_jina(query: str, recency: str | None = None, **_: Any) -> dict[str, Any]:
    return JinaClient().search(query)


def web_fetch_jina(url: str, **_: Any) -> dict[str, Any]:
    return JinaClient().fetch_url(url)


def web_fetch_tavily(url: str, **_: Any) -> dict[str, Any]:
    return TavilyClient().extract(url)


def news_search_tavily(query: str, date_range: str | None = None, **_: Any) -> dict[str, Any]:
    recency = (date_range or "week").split("-")[0] if date_range else "week"
    return TavilyClient().search(query, recency=recency, topic="news")


def news_search_jina(query: str, date_range: str | None = None, **_: Any) -> dict[str, Any]:
    return JinaClient().search(query)


def stock_quote_yfinance(ticker: str, **_: Any) -> dict[str, Any]:
    from tradingagents.dataflows.interface import route_to_vendor

    today = datetime.utcnow().strftime("%Y-%m-%d")
    brief = route_to_vendor("get_briefing_stock_info", ticker, today)
    info = yf.Ticker(ticker).info or {}
    return {
        "ticker": ticker,
        "brief": brief,
        "price": info.get("currentPrice") or info.get("regularMarketPrice"),
        "market_cap": info.get("marketCap"),
        "volume": info.get("volume"),
    }


def stock_quote_alpha_vantage(ticker: str, **_: Any) -> dict[str, Any]:
    from tradingagents.dataflows.interface import route_to_vendor

    today = datetime.utcnow().strftime("%Y-%m-%d")
    data = route_to_vendor("get_stock_data", ticker, today, today)
    if isinstance(data, str) and data.startswith("NO_DATA"):
        raise NoMarketDataError(symbol=ticker, detail=data)
    return {"ticker": ticker, "ohlcv": data}


def company_profile_yfinance(ticker: str, **_: Any) -> dict[str, Any]:
    info = yf.Ticker(ticker).info or {}
    if not info:
        raise NoMarketDataError(symbol=ticker, detail="no yfinance profile")
    return {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": info.get("exchange"),
        "description": (info.get("longBusinessSummary") or "")[:2000],
    }


def company_profile_fmp(ticker: str, **_: Any) -> dict[str, Any]:
    from tradingagents.equity_research.integrations.fmp import FMPClient

    client = FMPClient()
    if not client.available:
        raise VendorNotConfiguredError("FMP_API_KEY is not set")
    data = client._get(f"/profile/{ticker.upper()}")
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no FMP profile")
    row = data[0] if isinstance(data, list) else data
    return {"ticker": ticker, **row}


def financial_statement_fetch_yfinance(ticker: str, period: str = "annual", **_: Any) -> dict[str, Any]:
    from tradingagents.dataflows.interface import route_to_vendor

    today = datetime.utcnow().strftime("%Y-%m-%d")
    freq = "annual" if period == "annual" else "quarterly"
    return {
        "fundamentals": route_to_vendor("get_fundamentals", ticker, today),
        "income_statement": route_to_vendor("get_income_statement", ticker, freq, today),
        "balance_sheet": route_to_vendor("get_balance_sheet", ticker, freq, today),
        "cashflow": route_to_vendor("get_cashflow", ticker, freq, today),
    }


def financial_statement_fetch_alpha_vantage(ticker: str, period: str = "annual", **_: Any) -> dict[str, Any]:
    return financial_statement_fetch_yfinance(ticker, period)


def earnings_calendar_fmp(ticker: str, **_: Any) -> list[dict[str, Any]]:
    from tradingagents.equity_research.integrations.fmp import FMPClient

    client = FMPClient()
    if not client.available:
        raise VendorNotConfiguredError("FMP_API_KEY is not set")
    data = client.fetch_earnings_calendar(ticker)
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no earnings calendar")
    return data


def earnings_calendar_yfinance(ticker: str, **_: Any) -> list[dict[str, Any]]:
    cal = yf.Ticker(ticker).calendar
    if cal is None or (hasattr(cal, "empty") and cal.empty):
        raise NoMarketDataError(symbol=ticker, detail="no yfinance earnings calendar")
    if hasattr(cal, "to_dict"):
        return [cal.to_dict()]
    return [{"calendar": str(cal)}]


def analyst_estimates_fetch_fmp(ticker: str, **_: Any) -> dict[str, Any]:
    from tradingagents.equity_research.integrations.fmp import FMPClient

    client = FMPClient()
    if not client.available:
        raise VendorNotConfiguredError("FMP_API_KEY is not set")
    data = client._get(f"/analyst-estimates/{ticker.upper()}")
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no analyst estimates")
    return {"ticker": ticker, "estimates": data}


def analyst_estimates_fetch_info_sources(ticker: str, **_: Any) -> dict[str, Any]:
    from tradingagents.equity_research.integrations.info_sources import default_registry

    results = default_registry().fetch_all(ticker, "consensus")
    if not results:
        raise NoMarketDataError(symbol=ticker, detail="no consensus data")
    return results[0]


def analyst_estimates_fetch_yfinance(ticker: str, **_: Any) -> dict[str, Any]:
    return analyst_estimates_fetch_info_sources(ticker)


def transcript_search_fmp(ticker: str, quarter: str | None = None, **_: Any) -> list[dict[str, Any]]:
    from tradingagents.equity_research.integrations.fmp import FMPClient

    client = FMPClient()
    if not client.available:
        raise VendorNotConfiguredError("FMP_API_KEY is not set")
    data = client.fetch_earnings_call_transcripts(ticker)
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")
    return data


def transcript_search_perplexity(ticker: str, quarter: str | None = None, **_: Any) -> list[dict[str, Any]]:
    from tradingagents.llm_clients.perplexity_client import PerplexityClient

    client = PerplexityClient.from_config({})
    if not client.api_key:
        raise VendorNotConfiguredError("PERPLEXITY_API_KEY is not set")
    q = f"{ticker} earnings call transcript {quarter or 'latest'}"
    result = client.search(q)
    if not result.get("answer"):
        raise NoMarketDataError(symbol=ticker, detail="no perplexity transcript")
    return [{"ticker": ticker, "quarter": quarter, "content": result.get("answer", "")}]


def filings_search_edgar(ticker: str, form_type: str | None = None, **_: Any) -> list[dict[str, Any]]:
    from tradingagents.equity_research.integrations.edgar import EdgarClient

    forms = [form_type] if form_type else ["10-K", "10-Q", "8-K"]
    data = EdgarClient().fetch_recent_filings(ticker, forms)
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no filings")
    return data


def filing_reader_edgar(filing_url: str | None = None, filing_id: str | None = None, **_: Any) -> dict[str, Any]:
    url = filing_url or filing_id or ""
    if not url:
        raise NoMarketDataError(symbol="filing", detail="filing_url or filing_id required")
    return JinaClient().fetch_url(url)


def peer_comps_fetch_yfinance(ticker: str, **_: Any) -> dict[str, Any]:
    info = yf.Ticker(ticker).info or {}
    return {
        "ticker": ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "peers": [],
    }


def peer_comps_fetch_fmp(ticker: str, **_: Any) -> dict[str, Any]:
    from tradingagents.equity_research.integrations.fmp import FMPClient

    client = FMPClient()
    if not client.available:
        raise VendorNotConfiguredError("FMP_API_KEY is not set")
    data = client._get("/stock_peers", {"symbol": ticker.upper()})
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no peers")
    return {"ticker": ticker, "peers": data}


def valuation_multiples_fetch_yfinance(tickers: str | list[str], **_: Any) -> list[dict[str, Any]]:
    symbols = tickers if isinstance(tickers, list) else [t.strip() for t in tickers.split(",")]
    rows = []
    for sym in symbols:
        info = yf.Ticker(sym).info or {}
        rows.append({
            "ticker": sym,
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "price_to_book": info.get("priceToBook"),
        })
    if not rows:
        raise NoMarketDataError(symbol=str(tickers), detail="no multiples")
    return rows


def valuation_multiples_fetch_fmp(tickers: str | list[str], **_: Any) -> list[dict[str, Any]]:
    return valuation_multiples_fetch_yfinance(tickers)
