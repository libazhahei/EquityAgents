"""Fixed-size character chunking."""

from __future__ import annotations

from typing import Any

from tradingagents.rag.types import Chunk


class FixedSizeChunker:
    name = "fixed"

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        er = config.get("equity_research", config)
        self.chunk_size = int(er.get("rag_chunk_size", 1000))

    def chunk(self, text: str, *, metadata: dict[str, Any]) -> list[Chunk]:
        doc_key = metadata.get("doc_key", metadata.get("accession_number", "doc"))
        chunks: list[Chunk] = []
        for idx, start in enumerate(range(0, len(text), self.chunk_size)):
            body = text[start : start + self.chunk_size].strip()
            if not body:
                continue
            chunks.append(
                Chunk(
                    chunk_id=f"{doc_key}_{idx}",
                    text=body,
                    doc_key=doc_key,
                    chunk_index=idx,
                    metadata=dict(metadata),
                )
            )
        return chunks
