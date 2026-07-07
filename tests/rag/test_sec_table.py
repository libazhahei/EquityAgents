"""Tests for SEC table-aware chunking (SecTableChunker)."""

from __future__ import annotations

import pytest

from tradingagents.rag.chunking.sec_table import (
    SecTableChunker,
    _classify_line,
    _detect_table_regions,
    _extract_table_title,
    _is_label_only,
    _LineKind,
    _split_table_body_into_rows,
)

# ---------------------------------------------------------------------------
# Helper: build realistic SEC-style fixed-width table text
# ---------------------------------------------------------------------------


def _make_table_text(
    title: str = "Consolidated Balance Sheets",
    unit: str = "(In millions, except par value)",
    header: str = "Year Ended Jan 26, 2025 Jan 28, 2024",
    body_rows: list[str] | None = None,
    pre_paras: list[str] | None = None,
    post_paras: list[str] | None = None,
) -> str:
    """Build a realistic SEC-style text block with a fixed-width table."""
    parts: list[str] = []

    if pre_paras:
        for p in pre_paras:
            parts.append(p)
            parts.append("")  # blank line between paragraphs

    parts.append(title)
    parts.append(unit)
    parts.append(header)
    parts.append("─" * 80)

    if body_rows is None:
        body_rows = [
            "Assets",
            "Current assets:",
            f"Cash and cash equivalents{'':>20}{'$ 8,589':>20}{'$ 7,280':>20}",
            f"Marketable securities{'':>20}{'34,621':>20}{'18,704':>20}",
            f"Accounts receivable, net{'':>20}{'23,065':>20}{'9,999':>20}",
            f"Inventories{'':>20}{'10,080':>20}{'5,282':>20}",
            f"Prepaid expenses and other{'':>20}{'3,771':>20}{'3,080':>20}",
            f"Total current assets{'':>20}{'80,126':>20}{'44,345':>20}",
        ]

    for row in body_rows:
        parts.append(row)

    if post_paras:
        parts.append("")
        for p in post_paras:
            parts.append(p)

    return "\n".join(parts)


def _make_data_row(label: str, val1: str, val2: str) -> str:
    """Create a fixed-width data row that is >80 chars with far-right values."""
    return f"{label:<45}{val1:>20}{val2:>20}"


# ---------------------------------------------------------------------------
# Line classification tests
# ---------------------------------------------------------------------------


class TestLineClassification:
    def test_separator_line(self):
        assert _classify_line("─" * 80) == _LineKind.SEPARATOR
        assert _classify_line("=" * 60) == _LineKind.SEPARATOR
        assert _classify_line("━" * 40) == _LineKind.SEPARATOR

    def test_blank_line(self):
        assert _classify_line("") == _LineKind.BLANK
        assert _classify_line("   ") == _LineKind.BLANK

    def test_data_line(self):
        row = _make_data_row("Cash and cash equivalents", "$ 8,589", "$ 7,280")
        assert _classify_line(row) == _LineKind.DATA

    def test_label_line_short(self):
        assert _classify_line("Current assets:") == _LineKind.LABEL
        assert _classify_line("Assets") == _LineKind.LABEL

    def test_label_line_long_no_values(self):
        long_label = "This is a very long description label that has no numeric values on the right side at all"
        assert _classify_line(long_label) == _LineKind.LABEL


# ---------------------------------------------------------------------------
# Table detection tests
# ---------------------------------------------------------------------------


class TestTableDetection:
    def test_standard_table_detected(self):
        text = _make_table_text()
        lines = text.split("\n")
        tables = _detect_table_regions(lines)
        assert len(tables) == 1

    def test_small_table_not_split(self):
        """A table with only 5 body rows should still be detected as 1 table."""
        rows = [
            _make_data_row("Item A", "100", "200"),
            _make_data_row("Item B", "300", "400"),
            _make_data_row("Item C", "500", "600"),
            _make_data_row("Item D", "700", "800"),
            _make_data_row("Item E", "900", "1000"),
        ]
        text = _make_table_text(body_rows=rows)
        lines = text.split("\n")
        tables = _detect_table_regions(lines)
        assert len(tables) == 1

    def test_no_table_in_plain_text(self):
        text = "This is plain prose. It has no tables at all.\nJust paragraphs of text."
        lines = text.split("\n")
        tables = _detect_table_regions(lines)
        assert tables == []

    def test_two_tables_separated_by_blank_lines(self):
        rows = [_make_data_row("Item A", "100", "200")] * 4
        table1 = _make_table_text(title="Table One", body_rows=rows)
        table2 = _make_table_text(title="Table Two", body_rows=rows)
        combined = table1 + "\n\n\n" + table2  # ≥2 blank lines
        lines = combined.split("\n")
        tables = _detect_table_regions(lines)
        assert len(tables) == 2


# ---------------------------------------------------------------------------
# Table metadata extraction tests
# ---------------------------------------------------------------------------


class TestTableMetadata:
    def test_extract_title(self):
        text = _make_table_text(title="Consolidated Statements of Income")
        lines = text.split("\n")
        tables = _detect_table_regions(lines)
        assert len(tables) == 1
        title, unit = _extract_table_title(lines, tables[0][0])
        assert title == "Consolidated Statements of Income"
        assert unit == "(In millions, except par value)"

    def test_extract_title_no_unit(self):
        lines = [
            "Revenue Summary",
            "─" * 80,
            _make_data_row("Product A", "100", "200"),
            _make_data_row("Product B", "300", "400"),
            _make_data_row("Product C", "500", "600"),
        ]
        tables = _detect_table_regions(lines)
        assert len(tables) == 1
        title, unit = _extract_table_title(lines, tables[0][0])
        assert title == "Revenue Summary"


# ---------------------------------------------------------------------------
# Hierarchical label tracking tests
# ---------------------------------------------------------------------------


class TestHierarchicalLabels:
    def test_parent_label_tracking(self):
        """'Current assets:' should be a parent label for its child data rows."""
        body = [
            "Assets",
            "Current assets:",
            _make_data_row("Cash and cash equivalents", "$ 8,589", "$ 7,280"),
            _make_data_row("Marketable securities", "34,621", "18,704"),
            "Non-current assets:",
            _make_data_row("Property and equipment", "6,283", "3,914"),
            _make_data_row("Goodwill", "5,188", "4,430"),
        ]
        lines = [
            "Balance Sheet",
            "(In millions)",
            "─" * 80,
            *body,
        ]
        tables = _detect_table_regions(lines)
        assert len(tables) == 1
        rows = _split_table_body_into_rows(lines, tables[0][0], tables[0][1])
        # Find the data row for "Cash"
        cash_row = next(r for r in rows if "Cash" in r[0])
        assert "Current assets:" in cash_row[2]

    def test_label_only_detection(self):
        assert _is_label_only("Current assets:") is True
        assert _is_label_only(_make_data_row("Cash", "$ 8,589", "$ 7,280")) is False


# ---------------------------------------------------------------------------
# SecTableChunker integration tests
# ---------------------------------------------------------------------------


class TestSecTableChunker:
    def _config(self, rows_per_chunk=12, row_overlap=2):
        return {
            "table_rows_per_chunk": rows_per_chunk,
            "table_row_overlap": row_overlap,
            "table_context_paragraphs": 2,
            "filing_chunk_size": 300,
            "filing_chunk_overlap": 100,
        }

    def test_small_table_single_chunk(self):
        rows = [
            _make_data_row("Item A", "100", "200"),
            _make_data_row("Item B", "300", "400"),
            _make_data_row("Item C", "500", "600"),
            _make_data_row("Item D", "700", "800"),
            _make_data_row("Item E", "900", "1000"),
        ]
        text = _make_table_text(body_rows=rows)
        chunker = SecTableChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "test1"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) == 1
        assert table_chunks[0].metadata["table_title"] == "Consolidated Balance Sheets"

    def test_large_table_split_into_sub_chunks(self):
        """30 body rows → split into 3 sub-chunks at 12 rows/chunk."""
        rows = [
            _make_data_row(f"Row {i:02d}", f"{i*100:,}", f"{i*200:,}")
            for i in range(30)
        ]
        text = _make_table_text(body_rows=rows)
        chunker = SecTableChunker(self._config(rows_per_chunk=12, row_overlap=2))
        chunks = chunker.chunk(text, metadata={"doc_key": "test2"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) == 3

    def test_sub_chunks_have_overlap(self):
        """Adjacent sub-chunks share overlap rows."""
        rows = [
            _make_data_row(f"Row {i:02d}", f"{i*100:,}", f"{i*200:,}")
            for i in range(24)
        ]
        text = _make_table_text(body_rows=rows)
        chunker = SecTableChunker(self._config(rows_per_chunk=12, row_overlap=2))
        chunks = chunker.chunk(text, metadata={"doc_key": "test3"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        # With 24 rows, 12 per chunk, 2 overlap: chunks are rows 0-11, 10-21, 20-23
        assert len(table_chunks) == 3
        # The last 2 rows of chunk 1 should appear at the start of chunk 2
        lines_1 = table_chunks[0].text.split("\n")
        lines_2 = table_chunks[1].text.split("\n")
        # Find "Row 10" and "Row 11" (last 2 data rows of chunk 1)
        assert any("Row 10" in l for l in lines_1)
        assert any("Row 11" in l for l in lines_1)
        # They should also appear in chunk 2
        assert any("Row 10" in l for l in lines_2)
        assert any("Row 11" in l for l in lines_2)

    def test_continued_header_injects_parent_context(self):
        """Second chunk should have [Continued from:] with parent labels."""
        # Build a table where "Current assets:" appears early,
        # then many data rows follow — forcing a split.
        body: list[str] = ["Assets", "Current assets:"]
        for i in range(24):
            body.append(_make_data_row(f"Detail {i:02d}", f"{i*100:,}", f"{i*50:,}"))
        text = _make_table_text(body_rows=body)
        chunker = SecTableChunker(self._config(rows_per_chunk=12, row_overlap=2))
        chunks = chunker.chunk(text, metadata={"doc_key": "test4"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) >= 2
        # Second chunk should contain continuation marker
        assert "[Continued from:" in table_chunks[1].text
        # Parent context should reference "Current assets:"
        assert table_chunks[1].metadata.get("parent_labels") is not None

    def test_context_paragraphs_in_all_sub_chunks(self):
        """Context paragraphs from surrounding text appear in every sub-chunk."""
        rows = [
            _make_data_row(f"Row {i:02d}", f"{i*100:,}", f"{i*200:,}")
            for i in range(24)
        ]
        text = _make_table_text(
            body_rows=rows,
            pre_paras=["Item 8 presents our consolidated financial statements."],
            post_paras=["See accompanying Notes to the Consolidated Financial Statements."],
        )
        chunker = SecTableChunker(self._config(rows_per_chunk=12, row_overlap=2))
        chunks = chunker.chunk(text, metadata={"doc_key": "test5"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) >= 2
        for tc in table_chunks:
            assert "Context:" in tc.text
            assert "consolidated financial statements" in tc.text

    def test_folded_row_does_not_break_table(self):
        """A label row between DATA rows (folded/wrapped row) should not break the table."""
        body = [
            _make_data_row("Net income per share:", "", ""),  # folded label row
            _make_data_row("  Basic", "$ 3.10", "$ 1.21"),
            _make_data_row("  Diluted", "$ 3.05", "$ 1.19"),
            _make_data_row("Weighted avg shares (basic)", "24,500", "24,000"),
            _make_data_row("Weighted avg shares (diluted)", "24,800", "24,500"),
            _make_data_row("Dividends per share", "$ 0.00", "$ 0.00"),
        ]
        text = _make_table_text(body_rows=body)
        chunker = SecTableChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "test6"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        # Should be a single table, not broken up
        assert len(table_chunks) == 1

    def test_non_table_text_uses_paragraph_chunker(self):
        """Pure prose without tables should be chunked as text."""
        text = "\n\n".join(f"Paragraph {i} " + "word " * 200 for i in range(5))
        chunker = SecTableChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "test7"})
        assert len(chunks) > 0
        for c in chunks:
            assert c.metadata.get("chunk_type") == "text" or "section" in c.metadata

    def test_mixed_text_and_table(self):
        """Text with a table in the middle produces both text and table chunks."""
        rows = [_make_data_row(f"Row {i:02d}", f"{i*100:,}", f"{i*200:,}") for i in range(6)]
        pre = "This is the introductory paragraph before the table.\n\nIt has multiple sentences about revenue."
        table_text = _make_table_text(body_rows=rows)
        post = "The above table shows the key financial metrics for the period.\n\nFurther discussion follows."
        combined = pre + "\n\n" + table_text + "\n\n" + post
        chunker = SecTableChunker(self._config())
        chunks = chunker.chunk(combined, metadata={"doc_key": "test8"})
        types = {c.metadata.get("chunk_type") for c in chunks}
        assert "table" in types
        assert "text" in types

    def test_chunk_metadata_has_expected_fields(self):
        rows = [_make_data_row("Item A", "100", "200")] * 5
        text = _make_table_text(body_rows=rows)
        chunker = SecTableChunker(self._config())
        chunks = chunker.chunk(text, metadata={"doc_key": "test9", "section": "financial_statements"})
        table_chunks = [c for c in chunks if c.metadata.get("chunk_type") == "table"]
        assert len(table_chunks) >= 1
        tc = table_chunks[0]
        assert tc.metadata["chunk_type"] == "table"
        assert tc.metadata["table_title"] == "Consolidated Balance Sheets"
        assert tc.metadata["table_section"] == "financial_statements"
        assert "parent_labels" in tc.metadata
