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
        self.dim = int(er.get("embedding_dim", 1024))
        self.api_key = os.environ.get("OPENAI_API_KEY", "")
        self.base_url = self.config.get("backend_url") or "https://api.openai.com/v1"

    def embed(self, text: str) -> list[float]:
        if self.provider in ("openai", "openai_compatible", "qwen"):
            vec = self._api_embed(text)
            if vec:
                return vec
        return self._hash_embed(text)

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

    def _hash_embed(self, text: str) -> list[float]:
        """Deterministic fallback embedding for tests and offline use."""
        digest = hashlib.sha256(text.encode()).digest()
        vec = []
        for i in range(self.dim):
            byte = digest[i % len(digest)]
            vec.append((byte / 127.5) - 1.0)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]
