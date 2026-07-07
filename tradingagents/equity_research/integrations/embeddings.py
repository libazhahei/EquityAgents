"""Text embedding for evidence fragment vector search."""

from __future__ import annotations

import hashlib
import logging
import math
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class EmbeddingClient:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        er = self.config.get("equity_research", {})
        self.provider = er.get("embedding_provider", "hash")
        self.model = er.get("embedding_model", "text-embedding-v3")
        # Align default with default_config.py (1536) to avoid dimension mismatch
        self.dim = int(er.get("embedding_dim", 1536))
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.base_url = self.config.get("backend_url") or "https://api.openai.com/v1"

    def embed(self, text: str) -> list[float]:
        if self.provider in ("openai", "openai_compatible", "qwen"):
            vec = self._api_embed(text)
            if vec:
                return vec
        return self._hash_embed(text)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call when possible.

        Falls back to per-text embedding if the batch API call fails or
        if using the hash fallback.
        """
        if not texts:
            return []
        if self.provider in ("openai", "openai_compatible", "qwen") and self.api_key:
            vecs = self._api_embed_batch(texts)
            if vecs is not None:
                return vecs
        return [self._hash_embed(t) for t in texts]

    def _api_embed(self, text: str) -> list[float] | None:
        if not self.api_key:
            return None
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.base_url.rstrip('/')}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"model": self.model, "input": text[:8000]},
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
        except Exception as exc:
            logger.debug("Embedding API failed: %s", exc)
            return None

    def _api_embed_batch(self, texts: list[str], batch_size: int = 100) -> list[list[float]] | None:
        """Send multiple texts to the embedding API in batches.

        Most embedding APIs (OpenAI, Qwen, etc.) accept a list of inputs
        in a single request, which is far faster than N sequential calls.
        """
        if not self.api_key:
            return None

        all_embeddings: list[list[float]] = []
        try:
            with httpx.Client(timeout=60.0) as client:
                for i in range(0, len(texts), batch_size):
                    batch = [t[:8000] for t in texts[i:i + batch_size]]
                    response = client.post(
                        f"{self.base_url.rstrip('/')}/embeddings",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json={"model": self.model, "input": batch},
                    )
                    response.raise_for_status()
                    data = response.json()
                    # Sort by index to preserve input order (APIs return index field)
                    items = sorted(data["data"], key=lambda x: x["index"])
                    all_embeddings.extend(item["embedding"] for item in items)
            return all_embeddings
        except Exception as exc:
            logger.warning("Batch embedding API failed (%d texts): %s; falling back to per-text", len(texts), exc)
            return None

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic fallback embedding for tests and offline use."""
        digest = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(self.dim):
            byte = digest[i % len(digest)]
            vec.append((byte / 127.5) - 1.0)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
