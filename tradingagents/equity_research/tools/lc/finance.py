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
        "Filing section: financial_statements, income_statement, balance_sheet, cash_flow, mda, risk_factors, business, full(None)",
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
    filing_url: Annotated[str | None, "Direct SEC filing URL or accession number (e.g. 0000320193-24-000123)"] = None,
    filing_id: Annotated[str | None, "Filing accession number or URL alias"] = None,
    section: Annotated[
        str | None,
        "Section or item name to read. **Best workflow**: start with 'toc' to discover content, "
        "then use an item name from the response (e.g. 'mda', 'Item 6', 'Item 9'). "
        "Hardcoded aliases map automatically: 'item_7'/'management_discussion'→mda, "
        "'item_1a'→risk_factors, 'item_1'→business, 'item_8'/'statements'→financial_statements. "
        "Any arbitrary TOC item name is supported dynamically. "
        "Special values: 'toc' (discovery), 'tables' (render all tables), 'full' (raw text).",
    ] = None,
    ticker: Annotated[str | None, "Ticker symbol — browse recent filings by ticker + year/quarter instead of supplying a URL"] = None,
    year: Annotated[int | None, "Fiscal year (e.g. 2025), only meaningful with ticker"] = None,
    quarter: Annotated[str | None, "Fiscal quarter label (e.g. Q1, Q2, Q3, Q4), only meaningful with ticker"] = None,
    chunk_index: Annotated[int | None, "Page index for long narrative sections (mda, risk_factors, business). Default 0. Increment until has_more=False."] = None,
    table_index: Annotated[int | None, "When section='tables', targets one specific table by its numeric index (from toc['tables'] or the tables summary). Use negative for error-out when out of range."] = None,
) -> dict[str, Any]:
    """Read content from any SEC filing by direct URL/accession, or browse recent filings by ticker.

    === Recommended Agent Workflow ===

    1. **TOC** - call with ``section="toc"`` to learn the filing's chapter layout.
       Response includes ``available_items``, ``items_preview``, ``has_financials``, and
       a ``tables`` index with metadata for every table in the filing.

    2. **items_preview** - scan ``items_preview`` to find items of interest. Each entry shows
       ``{title, length, preview}`` so you can pick the most relevant sections.

    3. **Select & Read** - pass any item name from ``available_items`` directly as ``section``.
       The tool supports both hardcoded aliases and **arbitrary TOC items dynamically**:

       **Built-in aliases** (auto-resolved via ``_resolve_section_param``):

       | Alias / variant                     | Maps to                 | Description                |
       |-------------------------------------|-------------------------|----------------------------|
       | ``"mda"``, ``"item_7"``, ``"management_discussion"`` | ``"mda"`` (Item 7)        | MD&A text + tables         |
       | ``"risk_factors"``, ``"item_1a"``   | ``"risk_factors"`` (Item 1A) | Risk narratives            |
       | ``"business"``, ``"item_1"``        | ``"business"`` (Item 1)   | Company description        |
       | ``"financial_statements"``, ``"item_8"``, ``"statements"`` | ``"financial_statements"`` | All 3 statements         |
       | ``"income_statement"``              | XBRL Income             | Income statement DataFrame |
       | ``"balance_sheet"``                 | XBRL Balance Sheet      | Balance sheet DataFrame    |
       | ``"cash_flow"``                     | XBRL Cash Flow          | Cash flow statement DF     |

       **Arbitrary dynamic items** - any name from ``available_items`` works without pre-mapping:
       * ``"Item 6"`` (Selected Properties)
       * ``"Item 7A"`` (Market Risk Disclosure)
       * ``"Item 9"``, ``"Item 10"``, etc.
       * Any chapter the filing exposes but isn't in the hardcoded alias list.

    4. **Tables** - if you see an interesting non-financial table in TOC, jump to it:
       ``section="tables"``, ``table_index=N`` where N comes from ``toc["tables"]``.
       Or set ``section="tables"`` without ``table_index`` to paginate through all tables.

    5. **Long text pagination** - narrative sections exceeding ~30 kchars auto-chunk.
       Check ``has_more`` / ``total_chunks`` and advance with ``chunk_index=0, 1, 2, ...``.

    === Section Quick Reference ===

    * **toc** - Returns ``available_items`` (list of item names), ``items_preview`` (dict mapping item
      name → ``{title, length, preview, available}``), ``has_financials`` (bool), ``tables`` (index of
      every table with caption, type, row/col counts), and ``tables_summary`` ({total, by_type}).
      **Call this first** whenever you have a filing URL.

    * **financial_statements** - Income statement + balance sheet + cash flow as three Pandas DataFrames
      rendered to Markdown pipe tables (``content_format: "markdown_tables"``). Most reliable source
      thanks to XBRL-backed extraction.

    * **income_statement**, **balance_sheet**, **cash_flow** - Individual statements, same format.

    * **mda** - Management Discussion & Analysis (Item 7 for 10-K, Item 2 for 10-Q). Paginated text
      with embedded tables. Set ``chunk_index`` to page through long disclosures.

    * **risk_factors** - Item 1A narrative. Paginated text. Use ``chunk_index`` for multi-page results.

    * **business** - Item 1 narrative describing the company. Paginated text.

    * **tables** - Lists and renders every table in the filing. Without ``table_index``, returns all
      tables paginated (~30 kchars/chunk). With ``table_index=N``, returns exactly that table's
      Markdown rendering plus metadata (caption, row/col count, type). Non-financial tables
      (compensation, ownership, exhibit index, etc.) are discovered via TOC here.

    * **full** - Entire filing plain text (truncated at ~8 000 chars). Avoid unless nothing else works.

    === Usage Modes ===

    **By URL or accession**

    .. code-block:: python

       # Step 1: Discover content first
       r = filing_reader(filing_url="<url>", section="toc")
       print(r["available_items"])        # ["Item 1", "Item 1A", "Item 7", "Item 6", ...]
       print(r["items_preview"]["Item 6"])  # {title: "...", length: 12345, preview: "..."}
       print(r["tables_summary"])           # {"total": 47, "by_type": {"FINANCIAL": 3, ...}}

       # Step 2: Read specific sections -- built-in aliases
       filing_reader(filing_url="<url>", section="mda")
       filing_reader(filing_url="<url>", section="mda", chunk_index=1)     # paginate
       filing_reader(filing_url="<url>", section="income_statement")       # XBRL DataFrame

       # Step 2b: Read specific sections -- arbitrary TOC items (dynamic)
       filing_reader(filing_url="<url>", section="Item 6")                  # no alias needed!
       filing_reader(filing_url="<url>", section="Item 7A")
       filing_reader(filing_url="<url>", section="Item 9")

       # Step 3: Jump to non-financial tables
       filing_reader(filing_url="<url>", section="tables", table_index=12)  # exact table
       filing_reader(filing_url="<url>", section="tables")                   # all tables, paginated

    **Browse by ticker + period**

    .. code-block:: python

       listing = filing_reader(ticker="AAPL", year=2024, section="toc")
       listing = filing_reader(ticker="NVDA", year=2025, quarter="Q3", section="mda")

    When browsing by ticker, the result wraps multiple filings (one per form type) in a
    ``filings`` array alongside summary keys like ``count`` and ``ticker``.
    Each filing in the array carries ``form``, ``filing_date``, and ``url`` for downstream reads.
    """
    return finance_tools.filing_reader(
        filing_url=filing_url,
        filing_id=filing_id,
        section=section,
        ticker=ticker,
        year=year,
        quarter=quarter,
        chunk_index=chunk_index,
        table_index=table_index,
    )



@tool
def peer_comps_fetch(ticker: Annotated[str, "Ticker symbol"]) -> dict[str, Any]:
    """Fetch comparable peer companies.
    TOOL NOT IMPLEMENTED YET
    """
    return finance_tools.peer_comps_fetch(ticker)


@tool
def valuation_multiples_fetch(
    tickers: Annotated[str | list[str], "One ticker or comma-separated tickers"],
) -> Any:
    """Fetch valuation multiples for tickers.
    TOOL NOT IMPLEMENTED YET
    """
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
        year: Annotated[str | None, "Fiscal year, e.g. 2024"] = None,
        quarter: Annotated[str | None, "Fiscal quarter, e.g. Q1, Q2, Q3, Q4"] = None,
        top_k: Annotated[int, "Number of chunks to retrieve"] = 8,
        max_chars: Annotated[int, "Maximum total characters in results"] = 8000,
        dedupe: Annotated[bool, "Enable near-duplicate suppression"] = True,
        rerank: Annotated[bool, "Enable deterministic post-ranker"] = True,
        prefer_recent: Annotated[bool | None, "Bias recent-quarter intent to 10-Q"] = None,
        max_per_group: Annotated[int, "Max hits per filing/section/subsection group"] = 2,
    ) -> dict[str, Any]:
        """
    Search indexed SEC filings using hybrid BM25 + vector retrieval. 
    This is the tool that searches the filings database and returns relevant chunks of text based on the provided keywords and filters.

    Use this tool when you want explanations, drivers, risks, guidance, or filing-specific
    evidence from SEC documents. It is strongest when the query mirrors SEC wording and
    includes the company, time horizon, target topic, and filing context.

    Query guidance:
    - Include the ticker or company name plus the time window you care about, such as
      "FY2025", "Q3 2025", "recent quarters".
    - Prefer filing language over conversational wording. For example:
      "gross margin", "inventory provisions", "operating expenses", "revenue mix",
      "capital expenditures", "export controls", "liquidity", "guidance", "risk factors".
    - For management discussion and causal explanations, use `section="mda"`.
    - For table-like financial figures, use `section="financial_statements"` or a narrower
      statement section when possible. Recommand use other tools for financial data retrieval, such as `financial_statement_fetch` or `filing_reader`.
    - For risk or business model context, use `section="risk_factors"` or `section="business"`.
    - Avoid vague prompts like "what happened" or "why did it change" without the metric.
      Better: "drivers of gross margin decline year over year" or
      "inventory provisions impact on gross margin FY2025".
    - DO NOT EXPECT THIS TOOL TO ANSWER GENERAL QUESTIONS LIKE "What's the yoy growth" or "What is the business model".
        IF you do want to get growth, you should calculate it from the retrieved filings.

    Retrieval behavior:
    - `dedupe=True` suppresses near-duplicate chunks.
    - `rerank=True` applies a deterministic post-ranker that prefers substantive,
      explanatory chunks over boilerplate.
    - `prefer_recent=None` lets the tool infer recent-quarter intent from the query and bias
      toward 10-Q results when appropriate.
    - `max_per_group` limits repeated hits from the same filing/section/subsection group.

    Returned hits include `final_score`, `subsection_title`, `subsection_key`,
    `chunk_type`, and `dedupe_group` for debugging and evaluation.

    # Example usage:
    ticker = NVDA
    keywords = "revenue by segment data center gaming professional visualization automotive OEM and other product categories"
    form_type = 10-K
    year = 2025
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
            year=year,
            quarter=quarter,
        )

    filings_search_deps.name = "filings_search"
    return filings_search_deps
