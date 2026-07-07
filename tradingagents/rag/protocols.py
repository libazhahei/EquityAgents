"""Protocol definitions for pluggable RAG components."""

from __future__ import annotations

from typing import Any, Iterator, Protocol, runtime_checkable

from tradingagents.rag.types import Chunk, CorpusScope, Document, SearchHit


@runtime_checkable
class ChunkingStrategy(Protocol):
    name: str

    def chunk(self, text: str, *, metadata: dict[str, Any]) -> list[Chunk]: ...


@runtime_checkable
class CorpusLoader(Protocol):
    corpus_id: str

    def load(self, scope: CorpusScope) -> Iterator[Document]: ...

    def doc_key(self, doc: Document) -> str: ...

    def is_stale(self, doc: Document, backend: Any) -> bool: ...


@runtime_checkable
class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class IndexBackend(Protocol):
    def upsert_chunks(
        self,
        table: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        *,
        schema: dict[str, Any] | None = None,
    ) -> int: ...

    def delete_by_doc_key(self, table: str, doc_key: str, *, schema: dict[str, Any] | None = None) -> int: ...

    def is_indexed(self, table: str, doc_key: str, *, schema: dict[str, Any] | None = None) -> bool: ...

    def lexical_search(
        self,
        table: str,
        query: str,
        *,
        filters: dict[str, Any],
        top_k: int,
        schema: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    def vector_search(
        self,
        table: str,
        embedding: list[float],
        *,
        filters: dict[str, Any],
        top_k: int,
        schema: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...


@runtime_checkable
class FusionStrategy(Protocol):
    def fuse(
        self,
        rankings: list[list[tuple[str, float]]],
        *,
        k: int = 60,
    ) -> list[tuple[str, float]]: ...
