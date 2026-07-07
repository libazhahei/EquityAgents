"""Evidence fragment corpus loader."""

from __future__ import annotations

from typing import Any, Iterator

from tradingagents.rag.types import CorpusScope, Document


class EvidenceCorpus:
    corpus_id = "evidence"

    def __init__(self, config: dict[str, Any], evidence_store: Any | None = None):
        self.config = config
        self.evidence_store = evidence_store

    def load(self, scope: CorpusScope) -> Iterator[Document]:
        if scope.documents:
            for doc in scope.documents:
                yield doc
            return

        ticker = (scope.ticker or scope.filters.get("ticker", "")).upper()
        if not ticker or not self.evidence_store:
            return iter([])

        for row in self.evidence_store.list_by_ticker(ticker):
            fragment_id = row.get("fragment_id", "")
            hypothesis_id = scope.filters.get("hypothesis_id")
            if hypothesis_id and row.get("hypothesis_id") != hypothesis_id:
                continue
            frag_type = scope.filters.get("fragment_type")
            if frag_type and row.get("fragment_type") != frag_type:
                continue
            text = row.get("excerpt_text", "")
            if not text:
                continue
            yield Document(
                doc_key=fragment_id,
                text=text,
                metadata={
                    "ticker": ticker,
                    "fragment_id": fragment_id,
                    "doc_id": row.get("doc_id", ""),
                    "fragment_type": row.get("fragment_type", "general"),
                    "source_reliability": row.get("source_reliability", "medium"),
                    "hypothesis_id": row.get("hypothesis_id"),
                    "excerpt_context": row.get("excerpt_context", ""),
                },
            )

    def doc_key(self, doc: Document) -> str:
        return doc.doc_key or str(doc.metadata.get("fragment_id", "unknown"))

    def is_stale(self, doc: Document, backend: Any) -> bool:
        return True
