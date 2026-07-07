#!/usr/bin/env python3
"""Evaluate SEC filing RAG retrieval quality for a fixed query set."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from tradingagents.dataflows.config import get_config
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag

_DEFAULT_QUERIES = [
    ("gross margin", "mda"),
    ("gross margin recent quarters", "mda"),
    ("inventory provisions gross margin", "mda"),
]
_LOW_INFO_RE = re.compile(r"\b(?:refer\s+to|discussion\s+below|see\s+below)\b", re.I)


def _missing_required(hit: dict[str, Any]) -> bool:
    for field in ("form", "filing_date", "section", "accession_number"):
        value = hit.get(field)
        if value is None:
            return True
        if isinstance(value, str) and not value.strip():
            return True
    return False


def _dup_rate(hits: list[dict[str, Any]]) -> float:
    if not hits:
        return 0.0
    sigs = []
    for h in hits:
        text = " ".join(str(h.get("chunk_text", "")).lower().split())[:500]
        sigs.append(h.get("content_hash") or text)
    unique = len(set(sigs))
    return 1.0 - (unique / len(sigs))


def _top_low_info(hits: list[dict[str, Any]]) -> int:
    for idx, hit in enumerate(hits, start=1):
        text = str(hit.get("chunk_text", ""))
        if _LOW_INFO_RE.search(text):
            return idx
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate SEC filing RAG quality.")
    parser.add_argument("ticker", nargs="?", default="NVDA", help="Ticker symbol (default: NVDA)")
    parser.add_argument("--top-k", type=int, default=8, help="Top-k for retrieval (default: 8)")
    parser.add_argument("--max-chars", type=int, default=12000, help="Max chars per query (default: 12000)")
    parser.add_argument("--json", action="store_true", help="Print raw JSON report")
    args = parser.parse_args(argv)

    deps = EquityResearchDeps(config=get_config(), deep_llm=None, quick_llm=None)
    report: dict[str, Any] = {"ticker": args.ticker.upper(), "queries": [], "summary": {}}

    for query, section in _DEFAULT_QUERIES:
        result = filings_search_rag(
            deps,
            args.ticker,
            query,
            section=section,
            top_k=args.top_k,
            max_chars=args.max_chars,
            dedupe=True,
            rerank=True,
            prefer_recent=None,
            max_per_group=2,
        )
        hits = result.get("hits", [])
        item = {
            "query": query,
            "section": section,
            "hits": len(hits),
            "missing_metadata_hits": sum(1 for h in hits if _missing_required(h)),
            "dup_rate": round(_dup_rate(hits), 4),
            "low_info_rank": _top_low_info(hits),
            "top_forms": [h.get("form") for h in hits[:3]],
            "top_scores": [round(float(h.get("final_score", h.get("rrf_score", 0.0))), 6) for h in hits[:3]],
        }
        report["queries"].append(item)

    qs = report["queries"]
    report["summary"] = {
        "queries": len(qs),
        "total_missing_metadata_hits": sum(q["missing_metadata_hits"] for q in qs),
        "avg_dup_rate": round(sum(q["dup_rate"] for q in qs) / max(len(qs), 1), 4),
        "any_low_info_in_top3": any(0 < q["low_info_rank"] <= 3 for q in qs),
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Ticker: {report['ticker']}")
        print(f"Queries: {report['summary']['queries']}")
        print(f"Missing metadata hits: {report['summary']['total_missing_metadata_hits']}")
        print(f"Average duplicate rate: {report['summary']['avg_dup_rate']}")
        print(f"Low-info in top3: {report['summary']['any_low_info_in_top3']}")
        print()
        for q in report["queries"]:
            print(f"[{q['query']}] section={q['section']} hits={q['hits']}")
            print(
                f"  missing={q['missing_metadata_hits']} dup_rate={q['dup_rate']} "
                f"low_info_rank={q['low_info_rank']} top_forms={q['top_forms']}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
