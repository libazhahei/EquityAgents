"""LangChain finance tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import BaseTool, tool

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.tools import finance_tools
from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag


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
    query: Annotated[str | None, "Search query to filter the expected content in transcripts, " \
                                "vendor may provide summary based on query if available. " \
                                "Otherwise, all transcripts will be returned."] = None,
) -> Any:
    """Search earnings call transcripts."""
    return finance_tools.transcript_search(ticker, quarter=quarter, query=query)


@tool
def filings_search(
    ticker: Annotated[str, "Ticker symbol"],
    keywords: Annotated[str, "Search keywords — required; e.g. 'data center revenue growth FY2024'"],
    form_type: Annotated[str | None, "SEC form type, e.g. 10-K, 10-Q, 8-K"] = None,
    section: Annotated[
        str | None,
        "Filing section: financial_statements, income_statement, balance_sheet, cash_flow, mda, risk_factors, business, full",
    ] = None,
    top_k: Annotated[int, "Number of chunks to retrieve"] = 8,
    max_chars: Annotated[int, "Maximum total characters in results"] = 8000,
    dedupe: Annotated[bool, "Enable near-duplicate suppression"] = True,
    rerank: Annotated[bool, "Enable deterministic post-ranker"] = True,
    prefer_recent: Annotated[bool | None, "Bias recent-quarter intent to 10-Q"] = None,
    max_per_group: Annotated[int, "Max hits per filing/section/subsection group"] = 2,
) -> Any:
    """Search indexed SEC filings by keywords using hybrid BM25 + vector retrieval."""
    return finance_tools.filings_search(
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


@tool
def filing_reader(
    filing_url: Annotated[str | None, "Filing URL"] = None,
    filing_id: Annotated[str | None, "Filing id or URL alias"] = None,
    section: Annotated[
        str | None,
        "Filing section: financial_statements, income_statement, balance_sheet, cash_flow, mda, risk_factors, business, full",
    ] = None,
) -> dict[str, Any]:
    """Read filing content from URL, optionally scoped to a section."""
    return finance_tools.filing_reader(filing_url=filing_url, filing_id=filing_id, section=section)


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


def make_filings_search_tool(deps: EquityResearchDeps) -> BaseTool:
    @tool
    def filings_search_deps(
        ticker: Annotated[str, "Ticker symbol"],
        keywords: Annotated[str, "Search keywords — required; e.g. 'data center revenue growth'"],
        form_type: Annotated[str | None, "SEC form type, e.g. 10-K, 10-Q, 8-K"] = None,
        section: Annotated[
            str | None,
            "Filing section: mda, risk_factors, business, financial_statements, full",
        ] = None,
        top_k: Annotated[int, "Number of chunks to retrieve"] = 8,
        max_chars: Annotated[int, "Maximum total characters in results"] = 8000,
        dedupe: Annotated[bool, "Enable near-duplicate suppression"] = True,
        rerank: Annotated[bool, "Enable deterministic post-ranker"] = True,
        prefer_recent: Annotated[bool | None, "Bias recent-quarter intent to 10-Q"] = None,
        max_per_group: Annotated[int, "Max hits per filing/section/subsection group"] = 2,
    ) -> dict[str, Any]:
        """Search indexed SEC filings by keywords using hybrid BM25 + vector retrieval."""
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

    filings_search_deps.name = "filings_search"
    return filings_search_deps
