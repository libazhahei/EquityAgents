"""In-memory backend tests."""

from tradingagents.rag.backends.in_memory import InMemoryBackend
from tradingagents.rag.retrieval.hybrid import HybridRetriever
from tradingagents.rag.embedder import EmbeddingClientAdapter
from tradingagents.rag.types import Chunk, SearchQuery


class _HashEmbedder:
    def embed(self, text: str) -> list[float]:
        return [1.0, 0.0, 0.0] if "revenue" in text.lower() else [0.0, 1.0, 0.0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


def test_in_memory_ingest_and_hybrid_search():
    backend = InMemoryBackend()
    embedder = _HashEmbedder()
    chunks = [
        Chunk("c1", "Data center revenue grew 25% year over year.", "acc1", 0, {"ticker": "AAPL", "form": "10-K"}),
        Chunk("c2", "Risk factors include supply chain disruption.", "acc1", 1, {"ticker": "AAPL", "form": "10-K"}),
    ]
    embeddings = embedder.embed_batch([c.text for c in chunks])
    backend.upsert_chunks("filing_chunk", chunks, embeddings)

    retriever = HybridRetriever(backend, embedder)
    hits = retriever.search(
        "filing_chunk",
        SearchQuery(keywords="data center revenue", filters={"ticker": "AAPL"}, top_k=2),
    )
    assert hits
    assert "revenue" in hits[0].text.lower()
