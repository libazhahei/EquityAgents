"""Ingest SEC filings for a ticker/year into cache, document registry, and RAG index."""

from __future__ import annotations

from datetime import datetime

import logging
from typing import Any

from tradingagents.equity_research.integrations.sec_cache import write_filings_to_cache
from tradingagents.rag.types import CorpusScope, Document

logger = logging.getLogger(__name__)

DEFAULT_FORMS = ("10-K", "10-Q", "8-K")


def _extract_year_quarter(filing_date_str: str) -> tuple[str | None, str | None]:
    """Extract fiscal year label (e.g. FY2023) and quarter label (Q1-Q4) from a filing date string."""
    dt = _parse_filing_date(filing_date_str)
    if dt is None:
        return None, None
    year_label = f"FY{dt.year}"
    # 10-K filed Jan-Mar → Q4 of prior FY or current FY depending on convention
    # For simplicity use calendar-based quarter aligned to SEC form type
    month = dt.month
    quarter_map = {1: "Q4", 2: "Q4", 3: "Q1", 4: "Q1", 5: "Q2", 6: "Q2", 7: "Q3", 8: "Q3", 9: "Q4", 10: "Q4", 11: "Q1", 12: "Q1"}
    quarter = quarter_map.get(month)
    return year_label, quarter


def _parse_filing_date(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(str(value).strip(), fmt)
        except ValueError:
            continue
    return None


def filings_to_documents(ticker: str, filings: list[dict[str, Any]]) -> list[Document]:
    ticker = ticker.upper()
    documents: list[Document] = []
    for filing in filings:
        text = filing.get("full_text") or filing.get("text_excerpt", "")
        if not text:
            logger.warning(
                "Skipping empty filing %s %s",
                filing.get("form"),
                filing.get("accession_number"),
            )
            continue
        accession = str(filing.get("accession_number", filing.get("filing_date", "unknown")))
        form = filing.get("form", "")
        fy_label, fq_label = _extract_year_quarter(filing.get("filing_date"))
        
        # Determine year/quarter label based on form type
        if form == "10-K":
            year_label, quarter_label = fy_label, None
        else:
            # 10-Q: derive quarter from filing date
            year_label, quarter_label = fy_label, fq_label
        
        documents.append(
            Document(
                doc_key=accession,
                text=text,
                metadata={
                    "ticker": ticker,
                    "form": form,
                    "filing_date": filing.get("filing_date"),
                    "accession_number": accession,
                    "source_url": filing.get("url", ""),
                    "section": "full",
                    "year": year_label,
                    "quarter": quarter_label,
                },
            )
        )
    return documents


def ingest_ticker_filings_for_year(
    deps: Any,
    ticker: str,
    year: int,
    *,
    form_types: list[str] | None = None,
    force: bool = False,
    skip_rag: bool = False,
) -> dict[str, Any]:
    """
    Download all SEC filings for ``ticker`` in ``year``, cache locally,
    register documents, and index chunks into ``filing_chunk``.
    """
    ticker = ticker.upper()
    forms = form_types or list(DEFAULT_FORMS)

    filings = deps.edgar.fetch_filings_by_year(ticker, year, forms)
    if not filings:
        return {
            "ticker": ticker,
            "year": year,
            "forms": forms,
            "filings_found": 0,
            "documents_registered": 0,
            "chunks_indexed": 0,
            "skipped": 0,
            "errors": [],
        }

    write_filings_to_cache(deps.config, ticker, filings)
    documents = filings_to_documents(ticker, filings)

    registered = 0
    for filing in filings:
        deps.documents.register(
            ticker=ticker,
            source_type=filing.get("form", "10-K"),
            title=f"{ticker} {filing.get('form', '')} {filing.get('filing_date', '')}",
            source_url=filing.get("url", ""),
            published_date=filing.get("filing_date"),
        )
        registered += 1

    chunks_indexed = 0
    skipped = 0
    errors: list[str] = []
    if not skip_rag and deps.rag is not None:
        definition = deps.rag.registry.get("sec_filings")
        schema = definition.backend_schema()
        table = definition.table_name
        backend = deps.rag.backend

        if force:
            for doc in documents:
                try:
                    backend.delete_by_doc_key(table, doc.doc_key, schema=schema)
                except Exception as exc:
                    logger.debug("delete_by_doc_key %s: %s", doc.doc_key, exc)

        result = deps.rag.ingest(
            "sec_filings",
            CorpusScope(ticker=ticker, documents=documents),
        )
        chunks_indexed = result.chunks_indexed
        skipped = result.skipped
        errors = result.errors
    elif skip_rag:
        skipped = len(documents)

    return {
        "ticker": ticker,
        "year": year,
        "forms": forms,
        "filings_found": len(filings),
        "documents_registered": registered,
        "chunks_indexed": chunks_indexed,
        "skipped": skipped,
        "errors": errors,
        "filings": [
            {
                "form": f.get("form"),
                "filing_date": f.get("filing_date"),
                "accession_number": f.get("accession_number"),
                "text_chars": len(f.get("full_text") or f.get("text_excerpt") or ""),
            }
            for f in filings
        ],
    }
