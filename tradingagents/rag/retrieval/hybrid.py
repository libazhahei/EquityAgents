"""Hybrid retrieval combining lexical and vector search."""

from __future__ import annotations

from typing import Any

from tradingagents.rag.protocols import Embedder, FusionStrategy, IndexBackend
from tradingagents.rag.retrieval.fusion import RRFFusion
from tradingagents.rag.types import SearchHit, SearchQuery


class HybridRetriever:
    def __init__(
        self,
        backend: IndexBackend,
        embedder: Embedder,
        fusion: FusionStrategy | None = None,
        config: dict[str, Any] | None = None,
    ):
        self.backend = backend
        self.embedder = embedder
        self.fusion = fusion or RRFFusion()
        self.config = config or {}
        er = self.config.get("equity_research", {})
        self.rrf_k = int(er.get("rag_rrf_k", 60))

    def search(
        self,
        table: str,
        query: SearchQuery,
        *,
        schema: dict[str, Any] | None = None,
        text_column: str = "chunk_text",
        id_column: str = "chunk_id",
    ) -> list[SearchHit]:
        if not query.keywords.strip():
            return []

        filters = dict(query.filters)
        pool_k = query.pool_k

        lexical_hits = self.backend.lexical_search(
            table, query.keywords, filters=filters, top_k=pool_k, schema=schema
        )
        query_emb = self.embedder.embed(query.keywords)
        vector_hits = self.backend.vector_search(
            table, query_emb, filters=filters, top_k=pool_k, schema=schema
        )

        lexical_ranking = [(h.chunk_id, h.score) for h in lexical_hits]
        vector_ranking = [(h.chunk_id, h.score) for h in vector_hits]
        fused = self.fusion.fuse([lexical_ranking, vector_ranking], k=self.rrf_k)

        hit_map: dict[str, SearchHit] = {}
        for hit in lexical_hits + vector_hits:
            hit_map[hit.chunk_id] = hit

        results: list[SearchHit] = []
        for chunk_id, score in fused[: query.top_k]:
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
