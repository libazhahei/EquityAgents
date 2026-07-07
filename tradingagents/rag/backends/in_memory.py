"""In-memory index backend for tests."""

from __future__ import annotations

import math
import re
from typing import Any

from tradingagents.rag.types import Chunk, SearchHit


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (na * nb)


def _token_overlap(query: str, text: str) -> float:
    q = set(re.findall(r"\w+", query.lower()))
    t = set(re.findall(r"\w+", text.lower()))
    if not q or not t:
        return 0.0
    return len(q & t) / len(q)


class InMemoryBackend:
    """Simple in-memory store — lexical via token overlap, vector via cosine."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._tables: dict[str, list[dict[str, Any]]] = {}

    def _rows(self, table: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(table, [])

    def _schema(self, schema: dict[str, Any] | None) -> dict[str, Any]:
        return schema or {}

    def _text_col(self, schema: dict[str, Any]) -> str:
        return schema.get("text_column", "chunk_text")

    def _id_col(self, schema: dict[str, Any]) -> str:
        return schema.get("id_column", "chunk_id")

    def _doc_key_col(self, schema: dict[str, Any]) -> str:
        return schema.get("doc_key_column", "accession_number")

    def _match_filters(self, row: dict[str, Any], filters: dict[str, Any]) -> bool:
        for key, value in filters.items():
            if value is None:
                continue
            if str(row.get(key, "")).upper() != str(value).upper():
                return False
        return True

    def upsert_chunks(
        self,
        table: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        *,
        schema: dict[str, Any] | None = None,
    ) -> int:
        schema = self._schema(schema)
        doc_key_col = self._doc_key_col(schema)
        text_col = self._text_col(schema)
        id_col = self._id_col(schema)
        rows = self._rows(table)
        if chunks:
            doc_key = chunks[0].doc_key
            rows[:] = [r for r in rows if r.get(doc_key_col) != doc_key and r.get("doc_key") != doc_key]
        for chunk, emb in zip(chunks, embeddings):
            row = {**chunk.metadata, id_col: chunk.chunk_id, text_col: chunk.text, "doc_key": chunk.doc_key}
            row[doc_key_col] = chunk.doc_key
            row["embedding_vec"] = emb
            row["chunk_index"] = chunk.chunk_index
            rows.append(row)
        return len(chunks)

    def delete_by_doc_key(self, table: str, doc_key: str, *, schema: dict[str, Any] | None = None) -> int:
        schema = self._schema(schema)
        doc_key_col = self._doc_key_col(schema)
        rows = self._rows(table)
        before = len(rows)
        self._tables[table] = [
            r for r in rows if r.get(doc_key_col) != doc_key and r.get("doc_key") != doc_key
        ]
        return before - len(self._tables[table])

    def is_indexed(self, table: str, doc_key: str, *, schema: dict[str, Any] | None = None) -> bool:
        schema = self._schema(schema)
        doc_key_col = self._doc_key_col(schema)
        return any(
            r.get(doc_key_col) == doc_key or r.get("doc_key") == doc_key for r in self._rows(table)
        )

    def lexical_search(
        self,
        table: str,
        query: str,
        *,
        filters: dict[str, Any],
        top_k: int,
        schema: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        schema = self._schema(schema)
        text_col = self._text_col(schema)
        id_col = self._id_col(schema)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in self._rows(table):
            if not self._match_filters(row, filters):
                continue
            score = _token_overlap(query, row.get(text_col, ""))
            if score > 0:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                chunk_id=str(row[id_col]),
                text=str(row.get(text_col, "")),
                score=score,
                metadata={k: v for k, v in row.items() if k not in {text_col, "embedding_vec"}},
            )
            for score, row in scored[:top_k]
        ]

    def vector_search(
        self,
        table: str,
        embedding: list[float],
        *,
        filters: dict[str, Any],
        top_k: int,
        schema: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        schema = self._schema(schema)
        text_col = self._text_col(schema)
        id_col = self._id_col(schema)
        scored: list[tuple[float, dict[str, Any]]] = []
        for row in self._rows(table):
            if not self._match_filters(row, filters):
                continue
            vec = row.get("embedding_vec")
            if not vec:
                continue
            scored.append((_cosine(embedding, vec), row))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            SearchHit(
                chunk_id=str(row[id_col]),
                text=str(row.get(text_col, "")),
                score=score,
                metadata={k: v for k, v in row.items() if k not in {text_col, "embedding_vec"}},
            )
            for score, row in scored[:top_k]
        ]

    def get_row(self, table: str, chunk_id: str, *, schema: dict[str, Any] | None = None) -> dict[str, Any] | None:
        schema = self._schema(schema)
        id_col = self._id_col(schema)
        for row in self._rows(table):
            if str(row.get(id_col)) == chunk_id:
                return row
        return None
