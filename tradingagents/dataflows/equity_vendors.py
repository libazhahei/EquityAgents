"""Thin vendor wrappers delegating to integrations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import yfinance as yf

from tradingagents.dataflows.errors import (
    NoMarketDataError,
    VendorNotConfiguredError,
    VendorSubscriptionError,
)
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


def transcript_search_alpha_vantage(
    ticker: str,
    quarter: str | None = None,
    query: str | None = None,
    **_: Any,
) -> list[dict[str, Any]]:
    from tradingagents.dataflows.alpha_vantage_transcript import get_earnings_call_transcript

    data = get_earnings_call_transcript(ticker, quarter=quarter)
    if query:
        needle = query.strip().lower()
        data = [
            item for item in data
            if needle in str(item.get("content") or "").lower()
        ]
        if not data:
            raise NoMarketDataError(symbol=ticker, detail="no transcript match for query")
    return data


def transcript_search_fmp(ticker: str, quarter: str | None = None, **_: Any) -> list[dict[str, Any]]:
    from tradingagents.dataflows.config import get_config
    from tradingagents.equity_research.integrations.fmp import FMPClient, FMPSubscriptionError

    client = FMPClient(get_config())
    if not client.available:
        raise VendorNotConfiguredError("FMP_API_KEY is not set")
    try:
        data = client.fetch_earnings_call_transcripts(ticker, quarter=quarter)
    except FMPSubscriptionError as exc:
        raise VendorSubscriptionError(str(exc)) from exc
    if not data:
        raise NoMarketDataError(symbol=ticker, detail="no transcripts")
    return data


def transcript_search_perplexity(ticker: str, quarter: str | None = None, query: str | None = None, **_: Any) -> list[dict[str, Any]]:
    from tradingagents.llm_clients.perplexity_client import PerplexityClient

    client = PerplexityClient.from_config({})
    if not client.api_key:
        raise VendorNotConfiguredError("PERPLEXITY_API_KEY is not set")
    q = f"{ticker} earnings call transcript {quarter or 'latest'}"
    if query:
        q += f"Query: {query}"
    q += "Return the transcript content only, with keys: ticker, quarter, content."
    result = client.search(q)
    if not result.get("answer"):
        raise NoMarketDataError(symbol=ticker, detail="no perplexity transcript")
    return [{"ticker": ticker, "quarter": quarter, "content": result.get("answer", "")}]


def filings_search_edgar(
    ticker: str,
    form_type: str | None = None,
    section: str | None = None,
    keywords: str | None = None,
    top_k: int = 8,
    max_chars: int = 8000,
    dedupe: bool = True,
    rerank: bool = True,
    prefer_recent: bool | None = None,
    max_per_group: int = 2,
    **_: Any,
) -> dict[str, Any] | list[dict[str, Any]]:
    """Vendor fallback — RAG-backed search when keywords provided."""
    if not keywords or not keywords.strip():
        from tradingagents.dataflows.vendor_errors import NoMarketDataError

        raise NoMarketDataError(
            symbol=ticker,
            detail="keywords required for filings_search; use hybrid RAG retrieval",
        )
    from tradingagents.equity_research.agents.deps import EquityResearchDeps
    from tradingagents.dataflows.config import get_config
    from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag

    deps = EquityResearchDeps(config=get_config())
    return filings_search_rag(
        deps,
        ticker,
        keywords,
        form_type=form_type,
        section=section,
        top_k=top_k,
        max_chars=max_chars,
        dedupe=dedupe,
        rerank=rerank,
        prefer_recent=prefer_recent,
        max_per_group=max_per_group,
    )


def _resolve_section_param(section: str | None, target: str) -> str:
    """Map external section aliases to the canonical key that EdgarClient expects.

    The docstring lists user-friendly names like ``"mda"``, ``"risk_factors"``, etc.
    EdgarClient's ``read_filing_section`` already handles most of these natively,
    but some aliases need translating for consistency across the codebase.

    Known mappings:
    * ``"income_statement"``   → ``"income_statement"``
    * ``"balance_sheet"``      → ``"balance_sheet"``
    * ``"cash_flow"``          → ``"cash_flow"``
    * ``"financial_statements"`` → ``"financial_statements"``
    * ``"mda"``                → ``"mda"``       (Item 7)
    * ``"risk_factors"``       → ``"risk_factors"`` (Item 1A)
    * ``"business"``           → ``"business"``   (Item 1)
    * ``"toc"``                → ``"toc"``
    * ``"tables"``             → ``"tables"``
    * ``"full"``               → ``"full"``
    """
    if section is None or section == "full":
        return target if target else "full"
    s = section.strip().lower()
    # Direct passes-through — these are handled natively by EdgarClient
    allowed = {"toc", "full", "financial_statements", "income_statement",
               "balance_sheet", "cash_flow", "mda", "risk_factors",
               "business", "tables"}
    if s in allowed:
        return s
    # Common aliases → canonical names
    alias_map: dict[str, str] = {
        "item_7": "mda",
        "item7": "mda",
        "item 7": "mda",
        "management_discussion": "mda",
        "item_1a": "risk_factors",
        "item1a": "risk_factors",
        "item 1a": "risk_factors",
        "item_1": "business",
        "item1": "business",
        "item 1": "business",
        "item_8": "financial_statements",
        "item8": "financial_statements",
        "item 8": "financial_statements",
        "statements": "financial_statements",
        "statement": "financial_statements",
    }
    canonical = alias_map.get(s)
    if canonical:
        return canonical
    # Fallback: pass through as-is and let EdgarClient handle unknowns
    return s


def filing_reader_edgar(
    filing_url: str | None = None,
    filing_id: str | None = None,
    section: str | None = None,
    ticker: str | None = None,
    year: int | None = None,
    quarter: str | None = None,
    chunk_index: int | None = None,
    table_index: int | None = None,
    **extra: Any,
) -> dict[str, Any]:
    """Vendor implementation for filing_reader backed by EdgarClient.

    Supports two modes:
    1. **URL/accession** — read a specific filing's section.
    2. **Ticker browse** — list recent filings by ticker + period, optionally fetch section content.

    Additional parameters forwarded to :py:meth:`EdgarClient.read_filing_section`:
    * ``chunk_index`` — page index for narrative sections (default 0)
    * ``table_index`` — index of a specific table when section="tables"
    """
    from tradingagents.equity_research.integrations.edgar import EdgarClient

    # Merge any late-arriving kwargs from the routing layer
    ci = chunk_index if chunk_index is not None else extra.get("chunk_index")
    ti = table_index if table_index is not None else extra.get("table_index")
    sec = section

    # ---- mode: ticker + year/quarter (browse filings by date range) ----
    if ticker:
        client = EdgarClient()
        all_filings = client.fetch_filings_by_year(ticker, year or 2026)

        if not all_filings:
            return {
                "ticker": ticker.upper(),
                "year": year,
                "quarter": quarter,
                "section": sec or "full",
                "error": f"No filings found for {ticker} {year}",
                "filings": [],
            }

        # If quarter requested, only keep 10-Q with matching quarter
        filtered = []
        for f in all_filings:
            ft = f.get("form", "")
            fd = str(f.get("filing_date", ""))
            if quarter and quarter.upper().startswith("Q"):
                q_num = int(quarter[1])
                try:
                    parts = fd.split("-")[:3]
                    mm = int(parts[1]) if len(parts) >= 2 else 0
                    q = (mm - 1) // 3 + 1
                    if q != q_num or ft == "10-K":
                        continue
                except (ValueError, IndexError):
                    pass
            filtered.append(f)

        results = []
        for filing_meta in filtered:
            access = filing_meta.get("accession_number", "")
            if not access:
                continue
            result = client.read_filing_section(
                accession_number=access,
                section=_resolve_section_param(sec, "full"),
                chunk_index=ci or 0,
                table_index=ti,
            )
            result["form"] = filing_meta.get("form", result.get("form", ""))
            result["url"] = filing_meta.get("url", result.get("url", ""))
            result["filing_date"] = filing_meta.get("filing_date", result.get("filing_date", ""))
            results.append(result)

        return {
            "ticker": ticker.upper(),
            "year": year,
            "quarter": quarter,
            "section": sec or "full",
            "count": len(results),
            "filings": results,
        }

    # ---- mode: URL / accession-based (or item-based read via TOC reference) ----
    url = filing_url or filing_id or ""
    if not url:
        raise NoMarketDataError(symbol="filing", detail="filing_url or filing_id required")

    resolved_section = _resolve_section_param(sec, "full")

    result = EdgarClient().read_filing_section(
        filing_url=url if url.startswith("http") else None,
        accession_number=url if not url.startswith("http") else None,
        section=resolved_section,
        chunk_index=ci or 0,
        table_index=ti,
    )

    # Graceful fallback: if EDGAR parsing failed entirely, try fetching raw URL via Jina
    if result.get("error") and not result.get("text_excerpt"):
        from tradingagents.dataflows.jina_client import JinaClient

        raw_url = url if url.startswith("http") else (filing_url or "")
        jina_result = JinaClient().fetch_url(raw_url)
        if isinstance(jina_result, dict):
            return {**result, "_jina_fallback": True, "_raw_text": jina_result.get("content", jina_result.get("text", str(jina_result)))}
        return result

    return result



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
