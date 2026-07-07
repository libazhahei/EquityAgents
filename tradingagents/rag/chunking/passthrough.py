"""One chunk per document — for evidence excerpts."""

from __future__ import annotations

from typing import Any

from tradingagents.rag.types import Chunk


class PassthroughChunker:
    name = "passthrough"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def chunk(self, text: str, *, metadata: dict[str, Any]) -> list[Chunk]:
        doc_key = metadata.get("doc_key", metadata.get("fragment_id", "doc"))
        chunk_id = metadata.get("chunk_id", metadata.get("fragment_id", doc_key))
        if not text.strip():
            return []
        return [
            Chunk(
                chunk_id=str(chunk_id),
                text=text,
                doc_key=str(doc_key),
                chunk_index=0,
                metadata=dict(metadata),
            )
        ]
