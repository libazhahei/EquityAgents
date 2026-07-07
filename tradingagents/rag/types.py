"""Shared types for the RAG module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    chunk_id: str
    text: str
    doc_key: str
    chunk_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Document:
    doc_key: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CorpusScope:
    """Scope passed to corpus loaders for ingest."""

    ticker: str = ""
    filters: dict[str, Any] = field(default_factory=dict)
    documents: list[Document] = field(default_factory=list)


@dataclass
class SearchQuery:
    keywords: str
    filters: dict[str, Any] = field(default_factory=dict)
    top_k: int = 8
    max_chars: int = 8000
    pool_k: int = 30


@dataclass
class SearchHit:
    chunk_id: str
    text: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    corpus_id: str
    keywords: str
    hits: list[SearchHit] = field(default_factory=list)
    total_chars: int = 0
    indexed: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class IngestResult:
    corpus_id: str
    documents_processed: int = 0
    chunks_indexed: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
