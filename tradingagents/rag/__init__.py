"""Standalone RAG module for corpus ingest and hybrid retrieval."""

from tradingagents.rag.registry import CorpusRegistry
from tradingagents.rag.service import RAGService, build_rag_service
from tradingagents.rag.types import (
    Chunk,
    CorpusScope,
    Document,
    IngestResult,
    SearchHit,
    SearchQuery,
    SearchResult,
)

__all__ = [
    "Chunk",
    "CorpusRegistry",
    "CorpusScope",
    "Document",
    "IngestResult",
    "RAGService",
    "SearchHit",
    "SearchQuery",
    "SearchResult",
    "build_rag_service",
]
