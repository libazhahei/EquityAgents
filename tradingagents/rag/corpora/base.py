"""Corpus definition and loader base."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tradingagents.rag.chunking import get_chunker
from tradingagents.rag.protocols import ChunkingStrategy, CorpusLoader


@dataclass
class CorpusDefinition:
    corpus_id: str
    table_name: str
    loader: CorpusLoader
    chunker: ChunkingStrategy | str = "paragraph"
    schema: dict[str, Any] = field(default_factory=dict)
    filter_columns: tuple[str, ...] = ("ticker",)
    text_column: str = "chunk_text"
    id_column: str = "chunk_id"
    doc_key_column: str = "accession_number"
    vector_column: str = "embedding_vec"

    def resolve_chunker(self, config: dict[str, Any]) -> ChunkingStrategy:
        if isinstance(self.chunker, str):
            return get_chunker(self.chunker, config)  # type: ignore[return-value]
        return self.chunker

    def backend_schema(self) -> dict[str, Any]:
        return {
            "text_column": self.text_column,
            "id_column": self.id_column,
            "doc_key_column": self.doc_key_column,
            "vector_column": self.vector_column,
            **self.schema,
        }
