"""SEC Item-aware chunking — tags chunks with section metadata.

Integrates SecTableChunker for table-aware splitting within each section.
Detects and skips table-of-contents (TOC) blocks that produce false section
boundaries. Uses line-anchored regex to avoid matching "Item" references
inside running prose.
"""

from __future__ import annotations

import re
from typing import Any

from tradingagents.rag.chunking.sec_table import SecTableChunker
from tradingagents.rag.types import Chunk

# ---------------------------------------------------------------------------
# Section detection patterns — anchored to start of line
# ---------------------------------------------------------------------------

# Exclude lines that are referencing Items in running prose
_EXCLUDE_PATTERN = re.compile(
    r"(?:refer\s+to|pursuant\s+to|see\s+|in\s+accordance\s+with).*Item", re.I
)

_ITEM_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\s*ITEM\s+1A[\.\s\-–—]", re.I), "risk_factors"),
    (re.compile(r"^\s*ITEM\s+1B[\.\s\-–—]", re.I), "business"),
    (re.compile(r"^\s*ITEM\s+1C[\.\s\-–—]", re.I), "cybersecurity"),
    (re.compile(r"^\s*ITEM\s+1[\.\s\-–—]", re.I), "business"),
    (re.compile(r"^\s*ITEM\s+7A[\.\s\-–—]", re.I), "mda"),
    (re.compile(r"^\s*ITEM\s+7[\.\s\-–—]", re.I), "mda"),
    (re.compile(r"^\s*ITEM\s+8[\.\s\-–—]", re.I), "financial_statements"),
    (re.compile(r"^\s*ITEM\s+9A[\.\s\-–—]", re.I), "controls"),
]

_MDA_SUBSECTION_PATTERNS: list[tuple[re.Pattern[str], tuple[str, str]]] = [
    (
        re.compile(r"^\s*gross\s+profit\s+and\s+gross\s+margin\s*$", re.I),
        ("gross_profit_and_gross_margin", "Gross Profit and Gross Margin"),
    ),
    (re.compile(r"^\s*revenue\s*$", re.I), ("revenue", "Revenue")),
    (
        re.compile(r"^\s*operating\s+expenses?\s*$", re.I),
        ("operating_expenses", "Operating Expenses"),
    ),
    (
        re.compile(r"^\s*liquidity(?:\s+and\s+capital\s+resources)?\s*$", re.I),
        ("liquidity", "Liquidity and Capital Resources"),
    ),
    (
        re.compile(r"^\s*critical\s+accounting\s+estimates?\s*$", re.I),
        ("critical_accounting_estimates", "Critical Accounting Estimates"),
    ),
]


def detect_section(line: str) -> str | None:
    """Return the section name if *line* is a section header, else None."""
    if _EXCLUDE_PATTERN.search(line):
        return None
    for pattern, section in _ITEM_PATTERNS:
        if pattern.search(line):
            return section
    return None


def detect_mda_subsection(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text:
        return None
    for pattern, value in _MDA_SUBSECTION_PATTERNS:
        if pattern.match(text):
            return value
    return None


# ---------------------------------------------------------------------------
# TOC detection
# ---------------------------------------------------------------------------


def _find_toc_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """Find line ranges that are table-of-contents blocks.

    A TOC block is ≥4 Item header lines with ≤3 blank/non-Item lines between
    consecutive Item lines.
    """
    item_line_indices: list[int] = []
    for i, line in enumerate(lines):
        if detect_section(line) is not None:
            item_line_indices.append(i)

    if len(item_line_indices) < 4:
        return []

    # Find consecutive runs where spacing ≤ 3
    ranges: list[tuple[int, int]] = []
    run_start = 0
    for j in range(1, len(item_line_indices)):
        gap = item_line_indices[j] - item_line_indices[j - 1]
        if gap > 4:  # >3 lines between = gap of 4+
            # Check if current run qualifies
            if j - run_start >= 4:
                ranges.append(
                    (item_line_indices[run_start], item_line_indices[j - 1])
                )
            run_start = j

    # Check the final run
    if len(item_line_indices) - run_start >= 4:
        ranges.append(
            (item_line_indices[run_start], item_line_indices[-1])
        )

    return ranges


def _line_in_toc(line_idx: int, toc_ranges: list[tuple[int, int]]) -> bool:
    for start, end in toc_ranges:
        if start <= line_idx <= end:
            return True
    return False


def _split_mda_subsections(body: str) -> list[tuple[str, str, str]]:
    blocks: list[tuple[str, str, str]] = []
    current_key = "mda_general"
    current_title = "MD&A"
    buf: list[str] = []

    for line in body.splitlines():
        detected = detect_mda_subsection(line)
        if detected:
            if buf:
                blocks.append((current_key, current_title, "\n".join(buf)))
                buf = []
            current_key, current_title = detected
        buf.append(line)

    if buf:
        blocks.append((current_key, current_title, "\n".join(buf)))

    return blocks


# ---------------------------------------------------------------------------
# SecItemChunker
# ---------------------------------------------------------------------------


class SecItemChunker:
    name = "sec_item"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._table_chunker = SecTableChunker(config)

    def chunk(self, text: str, *, metadata: dict[str, Any]) -> list[Chunk]:
        doc_key = metadata.get("doc_key", metadata.get("accession_number", "doc"))
        current_section = metadata.get("section", "full")
        sections: list[tuple[str, str]] = []
        buffer: list[str] = []

        lines = text.splitlines()
        toc_ranges = _find_toc_ranges(lines)

        for i, line in enumerate(lines):
            if not _line_in_toc(i, toc_ranges):
                detected = detect_section(line)
                if detected:
                    if buffer:
                        sections.append((current_section, "\n".join(buffer)))
                        buffer = []
                    current_section = detected
            buffer.append(line)

        if buffer:
            sections.append((current_section, "\n".join(buffer)))

        if not sections:
            return self._table_chunker.chunk(text, metadata=metadata)

        chunks: list[Chunk] = []
        global_idx = 0
        for section, body in sections:
            if not body.strip():
                continue
            subsection_blocks: list[tuple[str, str, str]]
            if section == "mda":
                subsection_blocks = _split_mda_subsections(body)
            else:
                subsection_blocks = [(section, section, body)]

            for subsection_key, subsection_title, subsection_body in subsection_blocks:
                if not subsection_body.strip():
                    continue
                section_meta = {
                    **metadata,
                    "section": section,
                    "subsection_key": subsection_key,
                    "subsection_title": subsection_title,
                    "doc_key": doc_key,
                }
                for chunk in self._table_chunker.chunk(subsection_body, metadata=section_meta):
                    chunk.chunk_id = f"{doc_key}_{global_idx}"
                    chunk.chunk_index = global_idx
                    global_idx += 1
                    chunks.append(chunk)
        return chunks
