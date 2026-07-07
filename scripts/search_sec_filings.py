#!/usr/bin/env python3
"""Test hybrid retrieval over indexed SEC filings (BM25 + pgvector + RRF).

Usage:
    uv run python scripts/search_sec_filings.py NVDA "data center revenue growth"

    uv run python scripts/search_sec_filings.py AAPL "risk factors supply chain" --form 10-K --top-k 5

    uv run python scripts/search_sec_filings.py NVDA "gross margin" --section mda --json

    # Search evidence corpus instead of filings
    uv run python scripts/search_sec_filings.py NVDA "cloud revenue" --corpus evidence

Environment:
    TRADINGAGENTS_POSTGRES_URL   PostgreSQL + ParadeDB pg_search + pgvector
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import textwrap

from tradingagents.dataflows.config import get_config
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag
from tradingagents.rag.backends.pg_extensions import (
    check_docker_paradedb_status,
    format_docker_extension_status,
    format_extension_status,
    get_extension_status,
)
from tradingagents.rag.types import SearchQuery

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _truncate(text: str, width: int = 400) -> str:
    text = " ".join(text.split())
    if len(text) <= width:
        return text
    return text[: width - 3] + "..."


def _search_evidence(
    deps: EquityResearchDeps,
    ticker: str,
    keywords: str,
    *,
    top_k: int,
    max_chars: int,
) -> dict:
    if deps.rag is None:
        return {"error": "RAG service unavailable", "hits": []}
    result = deps.rag.search(
        "evidence",
        SearchQuery(
            keywords=keywords.strip(),
            filters={"ticker": ticker.upper()},
            top_k=top_k,
            max_chars=max_chars,
        ),
    )
    return {
        "corpus": "evidence",
        "ticker": ticker.upper(),
        "keywords": result.keywords,
        "hits": [
            {
                "chunk_text": h.text,
                "rrf_score": h.score,
                "fragment_id": h.metadata.get("fragment_id", h.chunk_id),
                "fragment_type": h.metadata.get("fragment_type"),
            }
            for h in result.hits
        ],
        "total_chars": result.total_chars,
        **result.extra,
    }


def _vector_only_search(
    deps: EquityResearchDeps,
    corpus: str,
    ticker: str,
    keywords: str,
    *,
    form_type: str | None,
    section: str | None,
    top_k: int,
    max_chars: int,
) -> dict:
    if deps.rag is None:
        return {"error": "RAG service unavailable", "hits": []}
    definition = deps.rag.registry.get(corpus)
    schema = definition.backend_schema()
    filters: dict = {"ticker": ticker.upper()}
    if form_type:
        filters["form"] = form_type
    if section:
        filters["section"] = section
    hits = deps.rag.backend.vector_search(
        definition.table_name,
        deps.rag.embedder.embed(keywords.strip()),
        filters=filters,
        top_k=top_k,
        schema=schema,
    )
    total = 0
    trimmed = []
    for h in hits:
        if total + len(h.text) > max_chars and trimmed:
            break
        trimmed.append(h)
        total += len(h.text)
    return {
        "corpus": corpus,
        "ticker": ticker.upper(),
        "keywords": keywords.strip(),
        "mode": "vector_only",
        "hits": [
            {
                "chunk_text": h.text,
                "rrf_score": h.score,
                "form": h.metadata.get("form"),
                "filing_date": h.metadata.get("filing_date"),
                "section": h.metadata.get("section"),
                "accession_number": h.metadata.get("accession_number"),
                "fragment_id": h.metadata.get("fragment_id", h.chunk_id),
                "fragment_type": h.metadata.get("fragment_type"),
            }
            for h in trimmed
        ],
        "total_chars": total,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test hybrid RAG retrieval over SEC filings or evidence.",
    )
    parser.add_argument("ticker", help="Stock ticker, e.g. NVDA")
    parser.add_argument("keywords", help='Search keywords, e.g. "data center revenue"')
    parser.add_argument(
        "--corpus",
        choices=("sec_filings", "evidence"),
        default="sec_filings",
        help="RAG corpus to search (default: sec_filings)",
    )
    parser.add_argument("--form", dest="form_type", default=None, help="Filter by form, e.g. 10-K")
    parser.add_argument(
        "--section",
        default=None,
        help="Filter by section tag, e.g. mda, risk_factors, business",
    )
    parser.add_argument("--top-k", type=int, default=8, help="Number of chunks to retrieve")
    parser.add_argument("--max-chars", type=int, default=500000, help="Max total chars returned (default: 500000)")
    parser.add_argument(
        "--dedupe",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable near-duplicate suppression (default: true)",
    )
    parser.add_argument(
        "--rerank",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable deterministic post-ranker (default: true)",
    )
    parser.add_argument(
        "--prefer-recent",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Bias recent-quarter intent to 10-Q (default: auto)",
    )
    parser.add_argument(
        "--max-per-group",
        type=int,
        default=2,
        help="Max hits per filing/section/subsection group (default: 2)",
    )
    parser.add_argument("--json", action="store_true", help="Print raw JSON result")
    parser.add_argument(
        "--use-memory",
        action="store_true",
        help="Use in-memory backend (for local testing without PostgreSQL)",
    )
    parser.add_argument(
        "--vector-only",
        action="store_true",
        help="Skip BM25; use pgvector cosine search only (useful without ParadeDB)",
    )
    parser.add_argument(
        "--snippet-width",
        type=int,
        default=100000,
        help="Max characters per hit preview in text mode (default: 100000, effectively unlimited)",
    )
    args = parser.parse_args(argv)

    if not args.keywords.strip():
        logger.error("keywords cannot be empty")
        return 1

    config = get_config()
    if args.use_memory:
        config["equity_research_use_memory"] = True

    ext_status = get_extension_status(config)
    docker_status = check_docker_paradedb_status()
    if args.json:
        pass  # merged into result below
    else:
        print(format_extension_status(ext_status))
        print()
        print(format_docker_extension_status(docker_status))
        print()

    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None)

    backend_name = type(deps.rag.backend).__name__ if deps.rag else "none"
    if not args.json:
        print(f"── RAG backend ──")
        print(f"  Selected: {backend_name}")
        print()
    logger.info("RAG backend: %s", backend_name)

    logger.info(
        "Searching corpus=%s ticker=%s keywords=%r form=%s section=%s vector_only=%s",
        args.corpus,
        args.ticker.upper(),
        args.keywords,
        args.form_type,
        args.section,
        args.vector_only,
    )

    if args.vector_only:
        result = _vector_only_search(
            deps,
            args.corpus,
            args.ticker,
            args.keywords,
            form_type=args.form_type,
            section=args.section,
            top_k=args.top_k,
            max_chars=args.max_chars,
        )
    elif args.corpus == "evidence":
        result = _search_evidence(
            deps,
            args.ticker,
            args.keywords,
            top_k=args.top_k,
            max_chars=args.max_chars,
        )
    else:
        result = filings_search_rag(
            deps,
            args.ticker,
            args.keywords,
            form_type=args.form_type,
            section=args.section,
            top_k=args.top_k,
            max_chars=args.max_chars,
            dedupe=args.dedupe,
            rerank=args.rerank,
            prefer_recent=args.prefer_recent,
            max_per_group=args.max_per_group,
        )
        result["corpus"] = "sec_filings"

    if args.json:
        result["postgres_extensions"] = ext_status
        result["docker_paradedb"] = docker_status
        result["rag_backend"] = backend_name
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result.get("error"):
            print(f"Error: {result['error']}")
        print(f"Corpus:       {result.get('corpus', args.corpus)}")
        print(f"Ticker:       {result.get('ticker', args.ticker.upper())}")
        print(f"Keywords:     {result.get('keywords', args.keywords)}")
        if result.get("mode"):
            print(f"Mode:         {result['mode']}")
        if "prefer_recent" in result:
            print(f"Prefer recent:{result['prefer_recent']}")
        print(f"Hits:         {len(result.get('hits', []))}")
        print(f"Total chars:  {result.get('total_chars', 0)}")
        print()
        for i, hit in enumerate(result.get("hits", []), start=1):
            score = hit.get("rrf_score", 0.0)
            final_score = hit.get("final_score", score)
            form = hit.get("form") or hit.get("fragment_type") or "?"
            date = hit.get("filing_date") or ""
            section = hit.get("section") or ""
            subsection = hit.get("subsection_key") or ""
            accession = hit.get("accession_number") or hit.get("fragment_id") or ""
            dedupe_group = hit.get("dedupe_group") or ""
            print(
                f"--- Hit {i}  rrf={score:.6f} final={final_score:.6f}  {form}  {date}  "
                f"{section}/{subsection}  {accession} ---"
            )
            if dedupe_group:
                print(f"Group: {dedupe_group}")
            snippet = _truncate(hit.get("chunk_text", ""), width=args.snippet_width)
            print(textwrap.fill(snippet, width=100))
            print()

    if result.get("error"):
        return 1
    if not result.get("hits"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
