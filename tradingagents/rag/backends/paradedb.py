"""ParadeDB BM25 + pgvector hybrid backend."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text

from tradingagents.rag.backends.pgvector import PgVectorBackend
from tradingagents.rag.retrieval.fusion import RRFFusion
from tradingagents.rag.types import SearchHit

logger = logging.getLogger(__name__)


class ParadeDBHybridBackend(PgVectorBackend):
    """BM25 via pg_search and pgvector cosine, with optional RRF in SQL."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config)
        er = (config or {}).get("equity_research", {})
        self.rrf_k = int(er.get("rag_rrf_k", 60))
        self.fusion = RRFFusion(k=self.rrf_k)

    def lexical_search(
        self,
        table: str,
        query: str,
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
        params: dict[str, Any] = {"q": query, "k": top_k}
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
                               paradedb.score({id_col}) AS score
                        FROM {table}
                        WHERE {text_col} @@@ :q{filter_sql}
                        ORDER BY score DESC
                        LIMIT :k
                        """
                    ),
                    params,
                )
                return self._rows_to_hits(result, id_col, text_col)
            except Exception as exc:
                logger.debug("ParadeDB lexical_search failed: %s", exc)
                raise

    def hybrid_search(
        self,
        table: str,
        query: str,
        embedding: list[float],
        *,
        filters: dict[str, Any],
        top_k: int,
        pool_k: int,
        schema: dict[str, Any] | None = None,
        search_year: str | None = None,
        search_quarter: str | None = None,
    ) -> list[SearchHit]:
        try:
            lexical = self.lexical_search(table, query, filters=filters, top_k=pool_k, schema=schema, search_year=search_year, search_quarter=search_quarter)
        except Exception as exc:
            logger.debug("BM25 search unavailable, falling back to vector only: %s", exc)
            lexical = []
        vector = self.vector_search(table, embedding, filters=filters, top_k=pool_k, schema=schema, search_year=search_year, search_quarter=search_quarter)
        if not lexical:
            return vector[:top_k]
        fused = self.fusion.fuse(
            [
                [(h.chunk_id, h.score) for h in lexical],
                [(h.chunk_id, h.score) for h in vector],
            ],
            k=self.rrf_k,
        )
        hit_map = {h.chunk_id: h for h in lexical + vector}
        results: list[SearchHit] = []
        for chunk_id, score in fused[:top_k]:
            base = hit_map.get(chunk_id)
            if base:
                results.append(
                    SearchHit(
                        chunk_id=chunk_id,
                        text=base.text,
                        score=score,
                        metadata={**base.metadata, "rrf_score": score},
                    )
                )
        return results
