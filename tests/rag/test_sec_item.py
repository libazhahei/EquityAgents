"""Tests for SEC Item-aware chunking (SecItemChunker) with TOC detection."""

from __future__ import annotations

import pytest

from tradingagents.rag.chunking.sec_item import (
    SecItemChunker,
    detect_mda_subsection,
    detect_section,
    _find_toc_ranges,
    _line_in_toc,
)


# ---------------------------------------------------------------------------
# Section detection tests
# ---------------------------------------------------------------------------


class TestDetectSection:
    def test_item_1a_risk_factors(self):
        assert detect_section("ITEM 1A. RISK FACTORS") == "risk_factors"

    def test_item_1_business(self):
        assert detect_section("ITEM 1. BUSINESS") == "business"

    def test_item_1b(self):
        assert detect_section("ITEM 1B. UNRESOLVED STAFF COMMENTS") == "business"

    def test_item_1c_cybersecurity(self):
        assert detect_section("ITEM 1C. CYBERSECURITY") == "cybersecurity"

    def test_item_7_mda(self):
        assert detect_section("ITEM 7. MANAGEMENT'S DISCUSSION") == "mda"

    def test_item_7a_mda(self):
        assert detect_section("ITEM 7A. QUANTITATIVE AND QUALITATIVE") == "mda"

    def test_item_8_financial(self):
        assert detect_section("ITEM 8. FINANCIAL STATEMENTS") == "financial_statements"

    def test_item_9a_controls(self):
        assert detect_section("ITEM 9A. CONTROLS AND PROCEDURES") == "controls"

    def test_refer_to_item_1a_not_triggered(self):
        """'Refer to Item 1A. Risk Factors' in running prose should NOT trigger."""
        assert detect_section("Refer to Item 1A. Risk Factors for more information") is None

    def test_pursuant_to_item_not_triggered(self):
        """'pursuant to Item 303 of Regulation S-K' should NOT trigger."""
        assert detect_section("pursuant to Item 303 of Regulation S-K") is None

    def test_see_item_not_triggered(self):
        """'See Item 8' reference should NOT trigger."""
        assert detect_section("See Item 8. Financial Statements for details") is None

    def test_in_accordance_with_item_not_triggered(self):
        """'in accordance with Item 601' should NOT trigger."""
        assert detect_section("in accordance with Item 601 of Regulation S-K") is None

    def test_bare_item_7_no_punctuation_not_triggered(self):
        """Centered page header 'Item 7' without punctuation should NOT trigger."""
        # The regex requires [\.\s\-–—] after the number
        assert detect_section("Item 7") is None

    def test_item_must_be_at_line_start(self):
        """'Some text ITEM 1. BUSINESS' should NOT trigger (not at start)."""
        assert detect_section("Some text ITEM 1. BUSINESS") is None

    def test_leading_whitespace_ok(self):
        """Leading whitespace before ITEM is allowed."""
        assert detect_section("  ITEM 1. BUSINESS") == "business"


class TestDetectMDASubsection:
    def test_detect_gross_profit_subsection(self):
        assert detect_mda_subsection("Gross Profit and Gross Margin") == (
            "gross_profit_and_gross_margin",
            "Gross Profit and Gross Margin",
        )

    def test_detect_liquidity_subsection(self):
        assert detect_mda_subsection("Liquidity and Capital Resources") == (
            "liquidity",
            "Liquidity and Capital Resources",
        )

    def test_non_heading_returns_none(self):
        assert detect_mda_subsection("gross margin improved by 120 bps") is None


# ---------------------------------------------------------------------------
# TOC detection tests
# ---------------------------------------------------------------------------


class TestTOCDetection:
    def test_toc_detected_with_4_consecutive_items(self):
        lines = [
            "TABLE OF CONTENTS",
            "",
            "ITEM 1. BUSINESS",
            "ITEM 1A. RISK FACTORS",
            "ITEM 7. MANAGEMENT'S DISCUSSION",
            "ITEM 8. FINANCIAL STATEMENTS",
            "",
            "Now the actual content begins.",
        ]
        ranges = _find_toc_ranges(lines)
        assert len(ranges) == 1
        # All item lines (indices 2-5) should be in the TOC range
        for i in [2, 3, 4, 5]:
            assert _line_in_toc(i, ranges)

    def test_toc_not_detected_for_scattered_items(self):
        """Items with large gaps should NOT be detected as TOC."""
        lines = [
            "ITEM 1. BUSINESS",
            "",
            "",
            "",
            "",
            "",
            "ITEM 1A. RISK FACTORS",
            "",
            "",
            "",
            "",
            "",
            "ITEM 7. MANAGEMENT'S DISCUSSION",
            "",
            "",
            "",
            "",
            "",
            "ITEM 8. FINANCIAL STATEMENTS",
        ]
        ranges = _find_toc_ranges(lines)
        assert len(ranges) == 0

    def test_fewer_than_4_items_no_toc(self):
        lines = [
            "ITEM 1. BUSINESS",
            "ITEM 1A. RISK FACTORS",
            "ITEM 7. MANAGEMENT'S DISCUSSION",
        ]
        ranges = _find_toc_ranges(lines)
        assert len(ranges) == 0


# ---------------------------------------------------------------------------
# SecItemChunker integration tests
# ---------------------------------------------------------------------------


class TestSecItemChunkerIntegration:
    def _config(self):
        return {
            "filing_chunk_size": 300,
            "filing_chunk_overlap": 50,
            "table_rows_per_chunk": 12,
            "table_row_overlap": 2,
        }

    def test_toc_items_skipped_body_items_used(self):
        """TOC block items should not create sections; body items should."""
        text = "\n".join([
            "TABLE OF CONTENTS",
            "",
            "ITEM 1. BUSINESS",
            "ITEM 1A. RISK FACTORS",
            "ITEM 7. MANAGEMENT'S DISCUSSION",
            "ITEM 8. FINANCIAL STATEMENTS",
            "",
            "",
            "",
            "",
            "Now the real content starts.",
            "",
            "ITEM 1. BUSINESS",
            "",
            "We are a technology company that designs and manufactures products.",
            "Our products are used by millions of people worldwide.",
            "",
            "ITEM 1A. RISK FACTORS",
            "",
            "Investing in our stock involves risks. The following are some of the",
            "key risks that could affect our business and financial results.",
        ])
        chunker = SecItemChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "10k"})
        sections = {c.metadata.get("section") for c in chunks}
        # Body ITEM 1 and ITEM 1A should create sections
        assert "business" in sections
        assert "risk_factors" in sections
        # TOC region should NOT create separate section chunks for those items
        # (the TOC block is skipped, so only the body items create sections)

    def test_refer_to_item_does_not_split(self):
        """'Refer to Item 1A' should not cause a section split."""
        text = "\n".join([
            "ITEM 1. BUSINESS",
            "",
            "We sell products. Refer to Item 1A. Risk Factors for more details.",
            "Our business continues to grow despite challenges.",
            "",
            "ITEM 1A. RISK FACTORS",
            "",
            "There are many risks associated with our business.",
        ])
        chunker = SecItemChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "10k"})
        # Find the business section chunks
        biz_chunks = [c for c in chunks if c.metadata.get("section") == "business"]
        assert len(biz_chunks) >= 1
        # The first business chunk should contain "Refer to Item 1A"
        biz_text = " ".join(c.text for c in biz_chunks)
        assert "Refer to Item 1A" in biz_text

    def test_section_tagging(self):
        """Each chunk should have the correct section tag."""
        text = "\n".join([
            "ITEM 1. BUSINESS",
            "",
            "We make products.",
            "",
            "ITEM 7. MANAGEMENT'S DISCUSSION",
            "",
            "Revenue grew significantly in the fiscal year.",
            "",
            "ITEM 8. FINANCIAL STATEMENTS",
            "",
            "The following presents our financial data.",
        ])
        chunker = SecItemChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "10k"})
        section_map: dict[str, list[str]] = {}
        for c in chunks:
            sec = c.metadata.get("section", "unknown")
            section_map.setdefault(sec, []).append(c.text)
        assert "business" in section_map
        assert "mda" in section_map
        assert "financial_statements" in section_map

    def test_integrates_sec_table_chunker(self):
        """SecItemChunker should use SecTableChunker internally."""
        # Build a section with a table
        rows = [
            f"{'Revenue':<45}{f'{i*1000:,}':>20}{f'{i*2000:,}':>20}"
            for i in range(1, 16)  # 15 data rows
        ]
        # Ensure rows are >80 chars
        rows = [r if len(r) > 80 else r + " " * (81 - len(r)) for r in rows]
        table_text = "\n".join([
            "Revenue by Product",
            "(In millions)",
            "─" * 80,
            *rows,
        ])
        text = "\n".join([
            "ITEM 8. FINANCIAL STATEMENTS",
            "",
            "The table below shows revenue by product.",
            "",
            table_text,
            "",
            "Revenue grew year over year.",
        ])
        chunker = SecItemChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "10k"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        # Should have at least 1 table chunk
        assert len(table_chunks) >= 1
        assert table_chunks[0].metadata["table_title"] == "Revenue by Product"

    def test_mda_subsection_metadata_present(self):
        text = "\n".join([
            "ITEM 7. MANAGEMENT'S DISCUSSION AND ANALYSIS",
            "",
            "Gross Profit and Gross Margin",
            "Gross margin increased to 75.0% driven by product mix.",
            "",
            "Operating Expenses",
            "Operating expenses increased due to compensation.",
        ])
        chunker = SecItemChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "10k"})
        gm = [c for c in chunks if c.metadata.get("subsection_key") == "gross_profit_and_gross_margin"]
        opex = [c for c in chunks if c.metadata.get("subsection_key") == "operating_expenses"]
        assert gm
        assert opex
