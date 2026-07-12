"""PostgreSQL pgvector backend with batch upsert optimization."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text

from tradingagents.rag.types import Chunk, SearchHit

logger = logging.getLogger(__name__)

# psycopg3 + SQLAlchemy: use CAST(...) not :param::vector (bind parser breaks on ::)
_VECTOR_EXPR = "CAST(:vec AS vector)"


class PgVectorBackend:
    """Generic pgvector upsert and cosine search."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._column_cache: dict[str, set[str]] = {}

    def _get_table_columns(self, table: str) -> set[str]:
        """Cache and return the set of column names for a table."""
        if table in self._column_cache:
            return self._column_cache[table]
        try:
            engine = self._engine()
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_name = :table"
                    ),
                    {"table": table},
                )
                cols = {row[0] for row in result}
            self._column_cache[table] = cols
            return cols
        except Exception:
            return set()  # fallback: no filtering

    def _engine(self):
        from tradingagents.equity_research.storage.db import get_engine
        return get_engine(self.config)

    def _schema(self, schema: dict[str, Any] | None) -> dict[str, Any]:
        return schema or {}

    def _text_col(self, schema: dict[str, Any]) -> str:
        return schema.get("text_column", "chunk_text")

    def _id_col(self, schema: dict[str, Any]) -> str:
        return schema.get("id_column", "chunk_id")

    def _doc_key_col(self, schema: dict[str, Any]) -> str:
        return schema.get("doc_key_column", "accession_number")

    def _vec_literal(self, embedding: list[float]) -> str:
        return "[" + ",".join(str(x) for x in embedding) + "]"

    def _build_filter_sql(self, filters: dict[str, Any], params: dict[str, Any]) -> str:
        clauses = []
        for i, (key, value) in enumerate(filters.items()):
            if value is None:
                continue
            pname = f"f_{key}_{i}"
            clauses.append(f"{key} = :{pname}")
            params[pname] = value if not isinstance(value, str) or key == "ticker" else value
            if key == "ticker":
                params[pname] = str(value).upper()
        return (" AND " + " AND ".join(clauses)) if clauses else ""

    def upsert_chunks(
        self,
        table: str,
        chunks: list[Chunk],
        embeddings: list[list[float]],
        *,
        schema: dict[str, Any] | None = None,
    ) -> int:
        """Bulk upsert chunks via batch INSERT.

        Performance improvement over the original per-chunk INSERT+UPDATE:
        - Vector is included directly in the INSERT (no separate UPDATE)
        - executemany sends all rows in one batch
        - Reduces 2*N queries to ceil(N/batch_size) queries
        """
        if not chunks:
            return 0
        schema = self._schema(schema)
        doc_key_col = self._doc_key_col(schema)
        text_col = self._text_col(schema)
        id_col = self._id_col(schema)
        vec_col = schema.get("vector_column", "embedding_vec")

        # Delete existing chunks for this document
        doc_key = chunks[0].doc_key
        self.delete_by_doc_key(table, doc_key, schema=schema)

        engine = self._engine()
        valid_cols = self._get_table_columns(table)
        if not valid_cols:
            valid_cols = {
                "ticker", "form", "filing_date", "accession_number",
                "section", "source_url", "doc_key", "doc_id",
                "chunk_type", "table_title", "table_section", "parent_labels",
                "subsection_title", "subsection_key", "word_count",
                "info_score_seed", "content_hash",
                "year", "quarter",
            }

        # Build rows for bulk insert
        rows: list[dict[str, Any]] = []
        for chunk, emb in zip(chunks, embeddings):
            meta = {}
            for k, v in chunk.metadata.items():
                if k in {id_col, text_col}:
                    continue
                if k not in valid_cols:
                    continue
                if isinstance(v, list):
                    meta[k] = json.dumps(v)
                else:
                    meta[k] = v

            row: dict[str, Any] = {
                id_col: chunk.chunk_id,
                text_col: chunk.text,
                doc_key_col: chunk.doc_key,
                "chunk_index": chunk.chunk_index,
                "created_at": datetime.utcnow(),
                **meta,
            }
            if schema.get("json_embedding"):
                row["embedding"] = json.dumps(emb)
            row["vec"] = self._vec_literal(emb)
            rows.append(row)

        if not rows:
            return 0

        # ── Normalize keys ──────────────────────────────────────────
        # executemany requires every row to have the *same* set of keys.
        # Some chunks (e.g. table chunks) carry extra metadata like
        # ``chunk_type`` that plain text chunks do not have.  We compute
        # the union of all keys and fill missing ones with ``None``.
        all_keys: set[str] = set()
        for row in rows:
            all_keys.update(row.keys())

        # Stable ordering: required columns first, then metadata columns
        # (keeps SQL readable and deterministic).
        required = {id_col, text_col, doc_key_col, "chunk_index", "created_at"}
        if schema.get("json_embedding"):
            required.add("embedding")
        col_keys = sorted(required) + sorted(all_keys - required - {"vec"})

        for row in rows:
            for k in col_keys:
                if k not in row:
                    row[k] = None

        # ── Build and execute SQL ────────────────────────────────────
        col_names = ", ".join(col_keys + [vec_col])
        placeholders = ", ".join(f":{c}" for c in col_keys) + ", CAST(:vec AS vector)"
        sql = text(f"INSERT INTO {table} ({col_names}) VALUES ({placeholders})")

        batch_size = 500
        count = 0
        with engine.connect() as conn:
            for i in range(0, len(rows), batch_size):
                batch = rows[i:i + batch_size]
                conn.execute(sql, batch)
                count += len(batch)
            conn.commit()
        return count

    def delete_by_doc_key(self, table: str, doc_key: str, *, schema: dict[str, Any] | None = None) -> int:
        schema = self._schema(schema)
        doc_key_col = self._doc_key_col(schema)
        engine = self._engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(f"DELETE FROM {table} WHERE {doc_key_col} = :dk OR doc_key = :dk"),
                {"dk": doc_key},
            )
            conn.commit()
            return result.rowcount or 0

    def is_indexed(self, table: str, doc_key: str, *, schema: dict[str, Any] | None = None) -> bool:
        schema = self._schema(schema)
        doc_key_col = self._doc_key_col(schema)
        engine = self._engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(f"SELECT 1 FROM {table} WHERE {doc_key_col} = :dk LIMIT 1"),
                {"dk": doc_key},
            )
            return result.first() is not None

    def vector_search(
        self,
        table: str,
        embedding: list[float],
        *,
        filters: dict[str, Any],
        top_k: int,
        schema: dict[str, Any] | None = None,
        search_year: str | None = None,
        search_quarter: str | None = None,
    ) -> list[SearchHit]:
        schema = self._schema(schema)
        text_col = self._text_col(schema)
        id_col = self._id_col(schema)
        vec_col = schema.get("vector_column", "embedding_vec")
        params: dict[str, Any] = {"vec": self._vec_literal(embedding), "k": top_k}
        if search_year is not None:
            params["year"] = search_year
        if search_quarter is not None:
            params["quarter"] = search_quarter
        # Merge year/quarter into filters so _build_filter_sql picks them up
        if search_year is not None and "year" not in filters:
            filters["year"] = search_year
        if search_quarter is not None and "quarter" not in filters:
            filters["quarter"] = search_quarter
        filter_sql = self._build_filter_sql(filters, params)
        engine = self._engine()
        with engine.connect() as conn:
            try:
                result = conn.execute(
                    text(
                        f"""
                        SELECT {id_col}, {text_col},
                               1 - ({vec_col} <=> {_VECTOR_EXPR}) AS score,
                               *
                        FROM {table}
                        WHERE {vec_col} IS NOT NULL{filter_sql}
                        ORDER BY {vec_col} <=> {_VECTOR_EXPR}
                        LIMIT :k
                        """
                    ),
                    params,
                )
                return self._rows_to_hits(result, id_col, text_col)
            except Exception as exc:
                logger.debug("vector_search failed: %s", exc)
                return []

    def lexical_search(
        self,
        table: str,
        query: str,
        *,
        filters: dict[str, Any],
        top_k: int,
        schema: dict[str, Any] | None = None,
    ) -> list[SearchHit]:
        return []

    @staticmethod
    def _rows_to_hits(result, id_col: str, text_col: str) -> list[SearchHit]:
        hits: list[SearchHit] = []
        for row in result:
            mapping = dict(row._mapping)
            hits.append(
                SearchHit(
                    chunk_id=str(mapping[id_col]),
                    text=str(mapping.get(text_col, "")),
                    score=float(mapping.get("score", 0.0)),
                    metadata={
                        k: v
                        for k, v in mapping.items()
                        if k not in {id_col, text_col, "score", "embedding_vec"}
                    },
                )
            )
        return hits
