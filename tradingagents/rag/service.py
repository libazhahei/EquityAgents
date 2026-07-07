"""High-level RAG ingest and search API."""

from __future__ import annotations

import hashlib
import logging
import re
import time
from typing import Any

from tradingagents.rag.embedder import EmbeddingClientAdapter
from tradingagents.rag.protocols import Embedder, IndexBackend
from tradingagents.rag.registry import CorpusRegistry
from tradingagents.rag.retrieval.hybrid import HybridRetriever
from tradingagents.rag.types import CorpusScope, IngestResult, SearchQuery, SearchResult

logger = logging.getLogger(__name__)
_REQUIRED_FILING_CHUNK_FIELDS = ("ticker", "form", "filing_date", "accession_number", "section", "chunk_type")
_LOW_INFO_RE = re.compile(r"\b(?:refer\s+to|see|discussion\s+below)\b", re.I)
_CAUSAL_RE = re.compile(r"\b(?:primarily|driven by|due to|because|as a result|offset by|impact)\b", re.I)
_NUMERIC_RE = re.compile(r"(?:\b\d+(?:\.\d+)?%|\$\s?\d[\d,]*(?:\.\d+)?)")


class RAGService:
    def __init__(
        self,
        registry: CorpusRegistry,
        embedder: Embedder,
        backend: IndexBackend,
        config: dict[str, Any] | None = None,
    ):
        self.registry = registry
        self.embedder = embedder
        self.backend = backend
        self.config = config or {}
        self._retriever = HybridRetriever(backend, embedder, config=self.config)

    @staticmethod
    def _normalize_text(text: str) -> str:
        return " ".join(text.lower().split())

    def _seed_info_score(self, text: str) -> float:
        normalized = self._normalize_text(text)
        words = normalized.split()
        if not words:
            return 0.0
        score = min(len(words) / 500.0, 1.0)
        if _CAUSAL_RE.search(text):
            score += 0.2
        if _NUMERIC_RE.search(text):
            score += 0.2
        if _LOW_INFO_RE.search(text):
            score -= 0.4
        if len(words) < 12:
            score -= 0.2
        return max(0.0, min(score, 1.0))

    def _enrich_chunk_metadata(self, chunk: Any) -> None:
        text = chunk.text or ""
        normalized = self._normalize_text(text)
        words = normalized.split()
        metadata = chunk.metadata
        metadata.setdefault("chunk_type", "text")
        metadata.setdefault("subsection_key", metadata.get("section", "full"))
        metadata.setdefault("subsection_title", metadata.get("section", "full"))
        metadata["word_count"] = len(words)
        metadata["info_score_seed"] = self._seed_info_score(text)
        metadata["content_hash"] = hashlib.sha1(normalized.encode("utf-8")).hexdigest()

    def _missing_filing_fields(self, chunk: Any) -> list[str]:
        missing: list[str] = []
        for field in _REQUIRED_FILING_CHUNK_FIELDS:
            value = chunk.metadata.get(field)
            if value is None:
                missing.append(field)
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(field)
        return missing

    def register(self, definition) -> None:
        self.registry.register(definition)

    def ingest(self, corpus_id: str, scope: CorpusScope) -> IngestResult:
        definition = self.registry.get(corpus_id)
        chunker = definition.resolve_chunker(self.config)
        schema = definition.backend_schema()
        table = definition.table_name
        result = IngestResult(corpus_id=corpus_id)

        # Pre-collect all documents and chunks for batch embedding
        all_docs = []
        all_chunks_by_doc: list[list[Any]] = []
        all_texts: list[str] = []
        doc_chunk_ranges: list[tuple[int, int]] = []  # (start, end) indices into all_texts

        for doc in definition.loader.load(scope):
            doc_key = definition.loader.doc_key(doc)
            if not definition.loader.is_stale(doc, self.backend) and self.backend.is_indexed(
                table, doc_key, schema=schema
            ):
                result.skipped += 1
                continue
            meta = {**doc.metadata, "doc_key": doc_key}
            chunks = chunker.chunk(doc.text, metadata=meta)
            if not chunks:
                continue
            if corpus_id == "sec_filings":
                filtered_chunks = []
                for chunk in chunks:
                    self._enrich_chunk_metadata(chunk)
                    missing = self._missing_filing_fields(chunk)
                    if missing:
                        result.errors.append(
                            f"{doc_key}:{chunk.chunk_id}: missing_required_metadata={','.join(missing)}"
                        )
                        continue
                    filtered_chunks.append(chunk)
                chunks = filtered_chunks
                if not chunks:
                    continue

            all_docs.append(doc)
            all_chunks_by_doc.append(chunks)
            start = len(all_texts)
            texts = [c.text for c in chunks]
            all_texts.extend(texts)
            doc_chunk_ranges.append((start, start + len(texts)))

        if not all_texts:
            return result

        # Batch embed all chunks across all documents in one go
        t0 = time.monotonic()
        logger.info(
            "Embedding %d chunks from %d documents in batch...",
            len(all_texts), len(all_docs),
        )
        all_embeddings = self.embedder.embed_batch(all_texts)
        embed_elapsed = time.monotonic() - t0
        logger.info(
            "Embedded %d chunks in %.1fs (%.0f chunks/s)",
            len(all_embeddings), embed_elapsed,
            len(all_embeddings) / max(embed_elapsed, 0.001),
        )

        # Bulk upsert per document
        t1 = time.monotonic()
        for i, doc in enumerate(all_docs):
            doc_key = definition.loader.doc_key(doc)
            chunks = all_chunks_by_doc[i]
            start, end = doc_chunk_ranges[i]
            embeddings = all_embeddings[start:end]

            try:
                count = self.backend.upsert_chunks(table, chunks, embeddings, schema=schema)
                result.chunks_indexed += count
                result.documents_processed += 1
                logger.info(
                    "Indexed %s: %d chunks", doc_key, count,
                )
            except Exception as exc:
                logger.warning("ingest failed for %s: %s", doc_key, exc)
                result.errors.append(f"{doc_key}: {exc}")

        upsert_elapsed = time.monotonic() - t1
        logger.info(
            "Upserted %d documents (%d chunks) in %.1fs",
            result.documents_processed, result.chunks_indexed, upsert_elapsed,
        )

        return result

    def search(self, corpus_id: str, query: SearchQuery) -> SearchResult:
        if not query.keywords or not query.keywords.strip():
            return SearchResult(
                corpus_id=corpus_id,
                keywords=query.keywords,
                hits=[],
                indexed=False,
                extra={"error": "keywords required"},
            )

        definition = self.registry.get(corpus_id)
        schema = definition.backend_schema()
        er = self.config.get("equity_research", {})
        top_k = query.top_k or int(er.get("rag_search_top_k", 8))
        max_chars = query.max_chars or int(er.get("rag_search_max_chars", 16000))
        pool_k = query.pool_k or int(er.get("rag_search_pool_k", 30))

        normalized = SearchQuery(
            keywords=query.keywords.strip(),
            filters=query.filters,
            top_k=top_k,
            max_chars=max_chars,
            pool_k=pool_k,
        )

        if hasattr(self.backend, "hybrid_search"):
            hits = self.backend.hybrid_search(
                definition.table_name,
                normalized.keywords,
                self.embedder.embed(normalized.keywords),
                filters=normalized.filters,
                top_k=normalized.top_k,
                pool_k=normalized.pool_k,
                schema=schema,
            )
        else:
            hits = self._retriever.search(
                definition.table_name,
                normalized,
                schema=schema,
                text_column=definition.text_column,
                id_column=definition.id_column,
            )

        total = 0
        trimmed = []
        for hit in hits:
            if total + len(hit.text) > max_chars and trimmed:
                # Allow the last hit to overshoot so we never return 0
                # meaningful hits just because a single chunk is large.
                trimmed.append(hit)
                total += len(hit.text)
                break
            trimmed.append(hit)
            total += len(hit.text)

        return SearchResult(
            corpus_id=corpus_id,
            keywords=normalized.keywords,
            hits=trimmed,
            total_chars=total,
            indexed=True,
        )


def build_rag_service(config: dict[str, Any], embeddings: Any) -> RAGService:
    from tradingagents.rag.backends import create_backend
    from tradingagents.equity_research.rag import register_equity_corpora

    registry = CorpusRegistry()
    register_equity_corpora(registry, config)
    backend = create_backend(config, use_memory=config.get("equity_research_use_memory", False))
    embedder = EmbeddingClientAdapter(embeddings)
    return RAGService(registry, embedder, backend, config=config)
