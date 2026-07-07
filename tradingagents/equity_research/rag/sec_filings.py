"""SEC filings corpus loader."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterator

from tradingagents.equity_research.integrations.sec_cache import load_cached_filings, sec_cache_dir
from tradingagents.rag.types import CorpusScope, Document

logger = logging.getLogger(__name__)


class SecFilingsCorpus:
    corpus_id = "sec_filings"

    def __init__(self, config: dict[str, Any], edgar: Any | None = None):
        self.config = config
        self.edgar = edgar

    def load(self, scope: CorpusScope) -> Iterator[Document]:
        if scope.documents:
            for doc in scope.documents:
                yield doc
            return

        ticker = (scope.ticker or scope.filters.get("ticker", "")).upper()
        if not ticker:
            return iter([])

        filings = load_cached_filings(self.config, ticker)
        if not filings and self.edgar:
            filings = self.edgar.fetch_recent_filings(
                ticker,
                scope.filters.get("form_types"),
                section="full",
            )

        form_filter = scope.filters.get("form") or scope.filters.get("form_type")
        for filing in filings:
            form = filing.get("form", "")
            if form_filter and form != form_filter:
                continue
            text = filing.get("full_text") or filing.get("text_excerpt", "")
            if not text:
                continue
            accession = str(filing.get("accession_number", filing.get("filing_date", "unknown")))
            yield Document(
                doc_key=accession,
                text=text,
                metadata={
                    "ticker": ticker,
                    "form": form,
                    "filing_date": filing.get("filing_date"),
                    "accession_number": accession,
                    "source_url": filing.get("url", ""),
                    "doc_id": filing.get("doc_id", ""),
                    "section": scope.filters.get("section", "full"),
                },
            )

    def doc_key(self, doc: Document) -> str:
        return doc.doc_key or str(doc.metadata.get("accession_number", "unknown"))

    def is_stale(self, doc: Document, backend: Any) -> bool:
        return False

    @staticmethod
    def cache_full_text(config: dict[str, Any], ticker: str, filings: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Persist full_text in sec cache JSON."""
        cache_dir = sec_cache_dir(config, ticker)
        cache_dir.mkdir(parents=True, exist_ok=True)
        updated: list[dict[str, Any]] = []
        for filing in filings:
            entry = dict(filing)
            accession = str(entry.get("accession_number", "")).replace("/", "-")
            form = entry.get("form", "filing")
            if entry.get("full_text") and len(entry["full_text"]) > 500_000:
                txt_path = cache_dir / f"{form}_{accession}.txt"
                txt_path.write_text(entry["full_text"], encoding="utf-8")
                entry["full_text_path"] = str(txt_path)
                entry.pop("full_text", None)
            path = cache_dir / f"{form}_{accession or entry.get('filing_date', 'unknown')}.json"
            path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
            if entry.get("full_text_path"):
                entry["full_text"] = Path(entry["full_text_path"]).read_text(encoding="utf-8")
            updated.append(entry)
        return updated
