"""RAGService end-to-end with in-memory backend."""

from __future__ import annotations

from typing import Any, Iterator

from tradingagents.rag.backends.in_memory import InMemoryBackend
from tradingagents.rag.corpora.base import CorpusDefinition
from tradingagents.rag.registry import CorpusRegistry
from tradingagents.rag.service import RAGService
from tradingagents.rag.types import CorpusScope, Document, SearchQuery


class _StubCorpus:
    corpus_id = "test_corpus"

    def load(self, scope: CorpusScope) -> Iterator[Document]:
        yield Document(
            doc_key="doc1",
            text="Cloud services revenue increased 30% in fiscal 2024.",
            metadata={"ticker": scope.ticker, "accession_number": "doc1"},
        )

    def doc_key(self, doc: Document) -> str:
        return doc.doc_key

    def is_stale(self, doc: Document, backend: Any) -> bool:
        return False


class _StubEmbedder:
    def embed(self, text: str) -> list[float]:
        return [0.5, 0.5, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def test_rag_service_ingest_and_search():
    registry = CorpusRegistry()
    registry.register(
        CorpusDefinition(
            corpus_id="test_corpus",
            table_name="test_table",
            loader=_StubCorpus(),
            chunker="passthrough",
            doc_key_column="accession_number",
        )
    )
    service = RAGService(registry, _StubEmbedder(), InMemoryBackend())
    ingest = service.ingest("test_corpus", CorpusScope(ticker="AAPL"))
    assert ingest.chunks_indexed >= 1

    result = service.search(
        "test_corpus",
        SearchQuery(keywords="cloud revenue", filters={"ticker": "AAPL"}),
    )
    assert result.hits
    assert "revenue" in result.hits[0].text.lower()


def test_rag_service_requires_keywords():
    registry = CorpusRegistry()
    registry.register(
        CorpusDefinition(
            corpus_id="test_corpus",
            table_name="test_table",
            loader=_StubCorpus(),
            chunker="passthrough",
        )
    )
    service = RAGService(registry, _StubEmbedder(), InMemoryBackend())
    result = service.search("test_corpus", SearchQuery(keywords=""))
    assert result.extra.get("error") == "keywords required"
