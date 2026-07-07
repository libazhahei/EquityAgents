"""Embedder adapters."""

from __future__ import annotations

from typing import Any


class EmbeddingClientAdapter:
    """Wrap equity research EmbeddingClient as RAG Embedder."""

    def __init__(self, client: Any):
        self._client = client

    def embed(self, text: str) -> list[float]:
        return self._client.embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        # Prefer the client's batch API for much faster ingestion
        if hasattr(self._client, "embed_batch"):
            return self._client.embed_batch(texts)
        return [self._client.embed(t) for t in texts]
