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
    """Search indexed SEC filings using hybrid BM25 + vector retrieval.

    Use this tool when you want explanations, drivers, risks, guidance, or filing-specific
    evidence from SEC documents. It is strongest when the query mirrors SEC wording and
    includes the company, time horizon, target topic, and filing context.

    Query guidance:
    - Include the ticker or company name plus the time window you care about, such as
      "FY2025", "Q3 2025", "recent quarters", or "year over year".
    - Prefer filing language over conversational wording. For example:
      "gross margin", "inventory provisions", "operating expenses", "revenue mix",
      "capital expenditures", "export controls", "liquidity", "guidance", "risk factors".
    - For management discussion and causal explanations, use `section="mda"`.
    - For table-like financial figures, use `section="financial_statements"` or a narrower
      statement section when possible.
    - For risk or business model context, use `section="risk_factors"` or `section="business"`.
    - Avoid vague prompts like "what happened" or "why did it change" without the metric.
      Better: "drivers of gross margin decline year over year" or
      "inventory provisions impact on gross margin FY2025".

    Retrieval behavior:
    - `dedupe=True` suppresses near-duplicate chunks.
    - `rerank=True` applies a deterministic post-ranker that prefers substantive,
      explanatory chunks over boilerplate.
    - `prefer_recent=None` lets the tool infer recent-quarter intent from the query and bias
      toward 10-Q results when appropriate.
    - `max_per_group` limits repeated hits from the same filing/section/subsection group.

    Returned hits include `final_score`, `subsection_title`, `subsection_key`,
    `chunk_type`, and `dedupe_group` for debugging and evaluation.
    """
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
        """Search indexed SEC filings using hybrid BM25 + vector retrieval.

        Use the same query style as `filings_search` above: SEC terms, explicit ticker,
        time window, and the most relevant filing section. For MD&A questions, keep the
        query anchored to the metric or event you want explained; for recent-quarter
        questions, include words like "recent", "latest", "quarter", or "trend" so the
        search can bias toward 10-Q filings when appropriate.
        """
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
