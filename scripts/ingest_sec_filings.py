#!/usr/bin/env python3
"""Ingest all SEC filings for a ticker and calendar year into PostgreSQL RAG index.

Downloads filings from EDGAR, writes local cache, registers documents, and
chunks/embeds into the ``filing_chunk`` table (ParadeDB BM25 + pgvector).

Usage:
    # Requires SEC_EDGAR_USER_AGENT and TRADINGAGENTS_POSTGRES_URL
    uv run python scripts/ingest_sec_filings.py NVDA 2023

    uv run python scripts/ingest_sec_filings.py NVDA 2024 --forms 10-K,10-Q

    # Re-index filings already in DB
    uv run python scripts/ingest_sec_filings.py MSFT 2023 --force

    # Drop and recreate tables (fixes schema/dimension mismatches)
    uv run python scripts/ingest_sec_filings.py NVDA 2025 --drop-tables --force

    # Download + cache only (no DB writes)
    uv run python scripts/ingest_sec_filings.py AAPL 2023 --skip-rag

Environment:
    SEC_EDGAR_USER_AGENT   Required by SEC EDGAR
    TRADINGAGENTS_POSTGRES_URL   PostgreSQL connection (unless --use-memory)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from tradingagents.dataflows.config import get_config
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.integrations.sec_ingest import (
    DEFAULT_FORMS,
    ingest_ticker_filings_for_year,
)
from tradingagents.equity_research.storage.db import drop_tables, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def parse_forms(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    return [f.strip() for f in raw.split(",") if f.strip()]


def parse_years(raw: str | None) -> list[int] | None:
    if not raw:
        return None
    years: list[int] = []
    for part in raw.split(","):
        value = part.strip()
        if not value:
            continue
        years.append(int(value))
    return years


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ingest SEC filings for a ticker and year into the RAG database.",
    )
    parser.add_argument("ticker", nargs="?", help="Stock ticker symbol, e.g. AAPL")
    parser.add_argument("year", nargs="?", type=int, help="Calendar year, e.g. 2023")
    parser.add_argument(
        "--forms",
        default=",".join(DEFAULT_FORMS),
        help=f"Comma-separated form types (default: {','.join(DEFAULT_FORMS)})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing chunks and re-index filings for this run",
    )
    parser.add_argument(
        "--drop-tables",
        action="store_true",
        help="Drop and recreate filing_chunk / evidence_fragment tables before ingestion "
             "(useful after schema changes or embedding dimension changes)",
    )
    parser.add_argument(
        "--rebuild-sec-index",
        action="store_true",
        help="Drop and recreate SEC index tables, then run ingestion (NVDA 2024-2026 10-K/10-Q by default)",
    )
    parser.add_argument(
        "--years",
        default=None,
        help="Comma-separated years for batch ingestion, e.g. 2024,2025,2026",
    )
    parser.add_argument(
        "--skip-rag",
        action="store_true",
        help="Download and cache only; skip PostgreSQL RAG indexing",
    )
    parser.add_argument(
        "--use-memory",
        action="store_true",
        help="Use in-memory storage instead of PostgreSQL (for testing)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print result as JSON",
    )
    args = parser.parse_args(argv)

    years = parse_years(args.years)
    ticker = args.ticker
    if years is None and args.year is not None:
        years = [args.year]
    if args.rebuild_sec_index:
        ticker = ticker or "NVDA"
        years = years or ([args.year] if args.year is not None else [2024, 2025, 2026])

    if not ticker:
        logger.error("ticker is required unless --rebuild-sec-index is used")
        return 1
    if not years:
        logger.error("year is required unless --years or --rebuild-sec-index provides defaults")
        return 1
    for y in years:
        if y < 1994 or y > 2100:
            logger.error("year must be between 1994 and 2100: %s", y)
            return 1

    config = get_config()
    if args.use_memory:
        config["equity_research_use_memory"] = True

    if not args.skip_rag and not args.use_memory:
        try:
            if args.drop_tables or args.rebuild_sec_index:
                logger.info("Dropping filing_chunk and evidence_fragment tables...")
                drop_tables(config, tables=["filing_chunk", "evidence_fragment"])
            init_db(config)
        except Exception as exc:
            logger.error("Database init failed: %s", exc)
            return 1

    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None)
    forms = parse_forms(args.forms)
    if args.rebuild_sec_index and args.forms == ",".join(DEFAULT_FORMS):
        forms = ["10-K", "10-Q"]

    logger.info(
        "Ingesting filings for %s years=%s (forms=%s, force=%s, skip_rag=%s, rebuild=%s)",
        ticker.upper(),
        years,
        forms,
        args.force,
        args.skip_rag,
        args.rebuild_sec_index,
    )
    run_results = []
    for year in years:
        run_results.append(
            ingest_ticker_filings_for_year(
                deps,
                ticker,
                year,
                form_types=forms,
                force=(args.force or args.rebuild_sec_index),
                skip_rag=args.skip_rag,
            )
        )
    result = {
        "ticker": ticker.upper(),
        "years": years,
        "forms": forms or [],
        "filings_found": sum(r["filings_found"] for r in run_results),
        "documents_registered": sum(r["documents_registered"] for r in run_results),
        "chunks_indexed": sum(r["chunks_indexed"] for r in run_results),
        "skipped": sum(r["skipped"] for r in run_results),
        "errors": [err for r in run_results for err in r.get("errors", [])],
        "filings": [f for r in run_results for f in r.get("filings", [])],
        "per_year": run_results,
    }

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Ticker:              {result['ticker']}")
        print(f"Years:               {', '.join(str(y) for y in result['years'])}")
        print(f"Forms:               {', '.join(result['forms'])}")
        print(f"Filings found:       {result['filings_found']}")
        print(f"Documents registered:{result['documents_registered']}")
        print(f"Chunks indexed:      {result['chunks_indexed']}")
        print(f"Skipped (cached):    {result['skipped']}")
        if result["errors"]:
            print("Errors:")
            for err in result["errors"]:
                print(f"  - {err}")
        if result.get("filings"):
            print("Filings:")
            for f in result["filings"]:
                print(
                    f"  {f['form']:6s} {f['filing_date']}  "
                    f"{f['accession_number']}  ({f['text_chars']:,} chars)"
                )

    if result["filings_found"] == 0:
        return 2
    if result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
