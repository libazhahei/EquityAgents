"""Tests for ParagraphChunker with sentence-level splitting."""

from __future__ import annotations

import pytest

from tradingagents.rag.chunking.paragraph import ParagraphChunker


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _word_count(text: str) -> int:
    return len(text.split())


def _make_sentence(min_words: int = 30) -> str:
    """Generate a realistic-looking sentence with ~min_words words."""
    words = [
        "The", "company", "reported", "strong", "revenue", "growth", "during",
        "the", "fiscal", "year", "driven", "by", "increased", "demand", "for",
        "its", "core", "products", "and", "services", "across", "all", "major",
        "markets", "including", "North", "America", "Europe", "and", "Asia",
    ]
    while len(words) < min_words:
        words.extend(["additionally", "the", "company", "expanded", "operations"])
    sentence = " ".join(words[:min_words])
    # Capitalize first word, add period
    return sentence[0].upper() + sentence[1:] + "."


# ---------------------------------------------------------------------------
# Basic chunking tests
# ---------------------------------------------------------------------------


class TestParagraphChunkerBasic:
    def test_small_paragraph_not_split(self):
        """A small paragraph (100 words) should not be split."""
        text = "word " * 100
        chunker = ParagraphChunker({"filing_chunk_size": 300, "filing_chunk_overlap": 50})
        chunks = chunker.chunk(text, metadata={"doc_key": "d1"})
        assert len(chunks) == 1
        assert _word_count(chunks[0].text) == 100

    def test_overlap_preserved(self):
        """Overlap words should appear at start of next chunk."""
        # Create 3 paragraphs of 150 words each, with chunk_size=200
        paras = [" ".join(f"para{i}word{j}" for j in range(150)) for i in range(3)]
        text = "\n\n".join(paras)
        chunker = ParagraphChunker({"filing_chunk_size": 200, "filing_chunk_overlap": 30})
        chunks = chunker.chunk(text, metadata={"doc_key": "d1"})
        assert len(chunks) >= 2
        # Check that overlap words from end of chunk 0 appear in chunk 1
        chunk0_words = chunks[0].text.split()
        chunk1_words = chunks[1].text.split()
        last_30_of_c0 = set(chunk0_words[-30:])
        first_words_of_c1 = set(chunk1_words[:50])
        overlap = last_30_of_c0 & first_words_of_c1
        assert len(overlap) > 0  # Some overlap exists

    def test_empty_text_returns_empty(self):
        chunker = ParagraphChunker({"filing_chunk_size": 300})
        chunks = chunker.chunk("", metadata={"doc_key": "d1"})
        assert chunks == []


# ---------------------------------------------------------------------------
# Sentence-level splitting tests
# ---------------------------------------------------------------------------


class TestSentenceSplitting:
    def test_oversized_paragraph_split_by_sentences(self):
        """A 600-word paragraph with 10 sentences should be split into 2-3 chunks."""
        sentences = [_make_sentence(min_words=60) for _ in range(10)]
        text = " ".join(sentences)
        assert _word_count(text) >= 580  # ~600 words
        chunker = ParagraphChunker({"filing_chunk_size": 300, "filing_chunk_overlap": 50})
        chunks = chunker.chunk(text, metadata={"doc_key": "d1"})
        assert len(chunks) >= 2
        # Each chunk should be ≤ ~350 words (allowing for overlap)
        for c in chunks:
            assert _word_count(c.text) <= 400

    def test_super_long_sentence_hard_split(self):
        """A 500-word sentence (no periods) should be hard-split."""
        words = [f"word{i}" for i in range(500)]
        text = " ".join(words)
        chunker = ParagraphChunker({"filing_chunk_size": 300, "filing_chunk_overlap": 50})
        chunks = chunker.chunk(text, metadata={"doc_key": "d1"})
        assert len(chunks) >= 2
        # All words should be preserved across chunks (minus overlap duplication)
        all_words = set()
        for c in chunks:
            all_words.update(c.text.split())
        for w in words:
            assert w in all_words

    def test_sentence_split_preserves_sentences(self):
        """Sentences should not be broken mid-sentence when possible."""
        # Build text with clear sentence boundaries
        sentences = [
            "The company reported strong revenue growth during the fiscal year driven by increased demand for its products.",
            "Operating expenses increased moderately due to strategic investments in research and development programs.",
            "Net income improved significantly compared to the prior fiscal year as a result of operational efficiency gains.",
            "Cash flow from operations remained robust providing flexibility for future capital allocation decisions and investments.",
            "The board of directors approved a new share repurchase program authorized for the coming fiscal year period ahead.",
        ]
        text = " ".join(sentences)
        chunker = ParagraphChunker({"filing_chunk_size": 50, "filing_chunk_overlap": 10})
        chunks = chunker.chunk(text, metadata={"doc_key": "d1"})
        assert len(chunks) >= 2
        # Each chunk should contain complete sentences (end with period)
        for c in chunks:
            stripped = c.text.strip()
            assert stripped.endswith(".") or stripped.endswith(",")


# ---------------------------------------------------------------------------
# Config default tests
# ---------------------------------------------------------------------------


class TestConfigDefaults:
    def test_default_chunk_size_is_300(self):
        """Default filing_chunk_size should be 300 words (not 800)."""
        chunker = ParagraphChunker({})
        assert chunker.chunk_size == 300

    def test_equity_research_nested_config(self):
        """Config nested under equity_research should be read."""
        chunker = ParagraphChunker({
            "equity_research": {
                "filing_chunk_size": 500,
                "filing_chunk_overlap": 50,
            }
        })
        assert chunker.chunk_size == 500
        assert chunker.overlap == 50

    def test_direct_config_keys(self):
        """Config without equity_research nesting should work too."""
        chunker = ParagraphChunker({
            "filing_chunk_size": 400,
            "filing_chunk_overlap": 75,
        })
        assert chunker.chunk_size == 400
        assert chunker.overlap == 75
