"""Tests for RAG chunking strategies."""

from tradingagents.rag.chunking import (
    FixedSizeChunker,
    ParagraphChunker,
    PassthroughChunker,
    SecItemChunker,
    SecTableChunker,
    get_chunker,
)


def test_paragraph_chunker_overlap():
    text = "\n\n".join(f"paragraph {i} " + "word " * 200 for i in range(5))
    chunker = ParagraphChunker({"filing_chunk_size": 100, "filing_chunk_overlap": 20})
    chunks = chunker.chunk(text, metadata={"doc_key": "acc1"})
    assert len(chunks) > 1
    assert all(c.doc_key == "acc1" for c in chunks)


def test_fixed_chunker():
    chunker = FixedSizeChunker({"rag_chunk_size": 50})
    chunks = chunker.chunk("a" * 120, metadata={"doc_key": "d1"})
    assert len(chunks) >= 2


def test_passthrough_chunker():
    chunker = PassthroughChunker()
    chunks = chunker.chunk("single excerpt", metadata={"fragment_id": "f1"})
    assert len(chunks) == 1
    assert chunks[0].chunk_id == "f1"


def test_sec_item_chunker_tags_section():
    text = "Preamble\n\nITEM 1. BUSINESS\n\nWe sell products.\n\nITEM 1A. RISK FACTORS\n\nMany risks."
    chunker = SecItemChunker({"filing_chunk_size": 50, "filing_chunk_overlap": 5})
    chunks = chunker.chunk(text, metadata={"doc_key": "10k"})
    sections = {c.metadata.get("section") for c in chunks}
    assert "business" in sections or "risk_factors" in sections


def test_get_chunker_returns_sec_table():
    chunker = get_chunker("sec_table")
    assert isinstance(chunker, SecTableChunker)


def test_get_chunker_falls_back_to_paragraph():
    chunker = get_chunker("nonexistent")
    assert isinstance(chunker, ParagraphChunker)
