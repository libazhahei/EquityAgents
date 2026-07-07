"""SEC table-aware chunking — detects fixed-width tables and splits them row-wise.

Handles:
- Table detection via separator / data / label / blank line classification
- Hierarchical parent-label tracking (indent-based stack)
- Row-level splitting with overlap
- Context paragraph attachment (pre/post)
- Non-table text delegation to ParagraphChunker
"""

from __future__ import annotations

import re
from typing import Any

from tradingagents.rag.chunking.paragraph import ParagraphChunker
from tradingagents.rag.types import Chunk

# ---------------------------------------------------------------------------
# Line classification
# ---------------------------------------------------------------------------

_SEPARATOR_RE = re.compile(r"^[━─\-–—=]{10,}\s*$")

# Value patterns that appear in fixed-width financial columns:
#   $1,234  (1,234)  12.3%  —  1,234,567  etc.
_VALUE_TOKEN_RE = re.compile(
    r"[\$€£]?\s*[\d,]+(?:\.\d+)?%?"        # $1,234 or 12.3%
    r"|(?:\([\d,]+(?:\.\d+)?\))"            # (1,234) — negative
    r"|—\s*$"                                # em-dash placeholder
)

_BLANK_RE = re.compile(r"^\s*$")

# Where "far right" numeric columns typically start in SEC text (character position).
_FAR_COL_THRESHOLD = 60


class _LineKind:
    SEPARATOR = "SEPARATOR"
    DATA = "DATA"
    LABEL = "LABEL"
    BLANK = "BLANK"


def _classify_line(line: str) -> str:
    """Classify a single line into SEPARATOR / DATA / LABEL / BLANK."""
    if _BLANK_RE.match(line):
        return _LineKind.BLANK
    if _SEPARATOR_RE.match(line):
        return _LineKind.SEPARATOR
    stripped = line.rstrip()
    if len(stripped) > 80:
        # Check for values in far-right columns
        tail = stripped[_FAR_COL_THRESHOLD:]
        if _VALUE_TOKEN_RE.search(tail):
            return _LineKind.DATA
        # Long line without far-right values — still might be a label or header row
        return _LineKind.LABEL
    # Short line: if it has any text, it is a label (or title, etc.)
    if stripped:
        return _LineKind.LABEL
    return _LineKind.BLANK


# ---------------------------------------------------------------------------
# Table detection
# ---------------------------------------------------------------------------


def _detect_table_regions(lines: list[str]) -> list[tuple[int, int]]:
    """Return a list of (start, end) index ranges that are tables.

    Algorithm:
    - Walk through the classified lines.
    - A table starts at a SEPARATOR or when we see ≥2 consecutive DATA rows.
    - A table ends after ≥2 consecutive BLANK rows or EOF.
    - Between DATA rows we tolerate up to 2 consecutive LABEL lines (folded
      headers / subtotals / wrapped labels).
    - Minimum table size: 3 lines.
    """
    kinds = [_classify_line(l) for l in lines]
    n = len(lines)
    tables: list[tuple[int, int]] = []
    i = 0

    while i < n:
        kind = kinds[i]

        # --- potential table start ---
        start: int | None = None
        if kind == _LineKind.SEPARATOR:
            start = i
        elif kind == _LineKind.DATA:
            # Look ahead for a second DATA within a small gap
            j = i + 1
            gap_labels = 0
            while j < n and gap_labels <= 2:
                if kinds[j] == _LineKind.DATA:
                    start = i
                    break
                elif kinds[j] == _LineKind.LABEL:
                    gap_labels += 1
                    j += 1
                elif kinds[j] == _LineKind.SEPARATOR:
                    start = i
                    break
                else:
                    break
        if start is None:
            i += 1
            continue

        # --- extend the table ---
        end = start
        consecutive_blanks = 0
        j = start + 1
        while j < n:
            k = kinds[j]
            if k == _LineKind.BLANK:
                consecutive_blanks += 1
                if consecutive_blanks >= 2:
                    break
                j += 1
                continue
            if k == _LineKind.SEPARATOR:
                consecutive_blanks = 0
                end = j
                j += 1
                continue
            if k == _LineKind.DATA:
                consecutive_blanks = 0
                end = j
                j += 1
                continue
            # LABEL — tolerate up to 2 between data lines
            if k == _LineKind.LABEL:
                # peek forward: is there DATA within 2 lines?
                peek_data = False
                for pj in range(j + 1, min(j + 3, n)):
                    if kinds[pj] in (_LineKind.DATA, _LineKind.SEPARATOR):
                        peek_data = True
                        break
                if peek_data:
                    consecutive_blanks = 0
                    end = j
                    j += 1
                    continue
                else:
                    # label not followed by data → table boundary
                    break
        # Minimum table size check
        table_len = end - start + 1
        if table_len >= 3:
            # Exclude pure TOC-like regions (no DATA rows at all)
            has_data = any(kinds[k] == _LineKind.DATA for k in range(start, end + 1))
            if has_data:
                tables.append((start, end))
        i = end + 1

    return tables


# ---------------------------------------------------------------------------
# Table metadata extraction
# ---------------------------------------------------------------------------


def _extract_table_title(lines: list[str], table_start: int) -> tuple[str, str]:
    """Extract (title, unit_note) from the lines preceding the table."""
    title = ""
    unit_note = ""
    # Scan backwards from table_start (up to 5 lines)
    search_start = max(0, table_start - 5)
    candidates = lines[search_start:table_start]
    # Find the first substantial line closest to the table as title
    # Scan backwards to find the title closest to the separator
    for ln in reversed(candidates):
        s = ln.strip()
        if not s or _SEPARATOR_RE.match(s):
            continue
        # Skip parentheticals like "(In millions)"
        if s.startswith("(") and s.endswith(")"):
            if not unit_note:
                unit_note = s
            continue
        # Skip lines that look like date headers (contain multiple years/dates)
        if re.search(r"\b(19|20)\d{2}.*\b(19|20)\d{2}", s) or re.search(r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec", s):
            continue
        # This is likely the title (closest to table)
        title = s
        break
    # Look for a unit note (parenthetical) if not found yet
    if not unit_note:
        paren_re = re.compile(r"^\s*(\([^)]+\))\s*$")
        for ln in candidates:
            m = paren_re.match(ln.strip())
            if m:
                unit_note = m.group(1)
                break
    # Also check first line of table body
    if not unit_note and table_start < len(lines):
        paren_re = re.compile(r"^\s*(\([^)]+\))\s*$")
        m = paren_re.match(lines[table_start].strip())
        if m:
            unit_note = m.group(1)
    return title, unit_note

def _extract_header_rows(lines: list[str], table_start: int, table_end: int) -> list[str]:
    """Extract header rows = non-blank lines before the first SEPARATOR inside the table."""
    headers: list[str] = []
    for i in range(table_start, table_end + 1):
        line = lines[i]
        if _SEPARATOR_RE.match(line):
            # Include the separator itself
            headers.append(line)
            break
        s = line.strip()
        if s:
            headers.append(line)
        else:
            break
    return headers


def _extract_context_paragraphs(
    lines: list[str], table_start: int, table_end: int, num_context: int
) -> list[str]:
    """Extract up to *num_context* paragraphs before the table.

    We intentionally avoid attaching trailing paragraphs because they
    frequently belong to the next subsection and cause noisy spillover.
    """
    before_paras: list[str] = []

    # Before: walk backwards from table_start
    buf: list[str] = []
    i = table_start - 1
    while i >= 0 and len(before_paras) < num_context:
        s = lines[i].strip()
        if s:
            buf.insert(0, s)
        else:
            if buf:
                before_paras.insert(0, " ".join(buf))
                buf = []
            if len(before_paras) >= num_context:
                break
        i -= 1
    if buf and len(before_paras) < num_context:
        before_paras.insert(0, " ".join(buf))

    return before_paras


# ---------------------------------------------------------------------------
# Hierarchical parent-label tracking
# ---------------------------------------------------------------------------


def _leading_spaces(line: str) -> int:
    return len(line) - len(line.lstrip())


def _is_label_only(line: str) -> bool:
    """True if the line is purely textual (no far-right numeric values)."""
    stripped = line.rstrip()
    if not stripped:
        return False
    if _SEPARATOR_RE.match(stripped):
        return False
    tail = stripped[_FAR_COL_THRESHOLD:] if len(stripped) > _FAR_COL_THRESHOLD else ""
    return not bool(_VALUE_TOKEN_RE.search(tail))


def _split_table_body_into_rows(
    lines: list[str], table_start: int, table_end: int
) -> list[tuple[str, str, list[str]]]:
    """Walk body rows after headers, returning (raw_line, kind, parent_context).

    parent_context is a list of hierarchical labels active when the row is seen.
    """
    # Determine where the body starts (after the first separator or header rows)
    body_start = table_start
    for i in range(table_start, table_end + 1):
        if _SEPARATOR_RE.match(lines[i]):
            body_start = i + 1
            break
    else:
        # No separator found — body starts after first non-blank non-header lines
        # Use heuristic: skip first 2 non-blank lines as headers
        skipped = 0
        for i in range(table_start, table_end + 1):
            if lines[i].strip():
                skipped += 1
                if skipped >= 2:
                    body_start = i + 1
                    break

    parent_stack: list[tuple[int, str]] = []  # (indent_level, label_text)
    rows: list[tuple[str, str, list[str]]] = []

    for i in range(body_start, table_end + 1):
        line = lines[i]
        kind = _classify_line(line)
        if kind == _LineKind.BLANK or kind == _LineKind.SEPARATOR:
            continue

        if _is_label_only(line):
            indent = _leading_spaces(line)
            # Pop labels at same or deeper indent
            while parent_stack and parent_stack[-1][0] >= indent:
                parent_stack.pop()
            parent_stack.append((indent, line.strip()))
            rows.append((line, "LABEL", [lbl for _, lbl in parent_stack]))
        else:
            # DATA row
            ctx = [lbl for _, lbl in parent_stack]
            rows.append((line, "DATA", ctx))

    return rows


# ---------------------------------------------------------------------------
# SecTableChunker
# ---------------------------------------------------------------------------


class SecTableChunker:
    """Table-aware chunker for SEC filings.

    Detects fixed-width financial tables, splits them into row-wise chunks
    with header injection, overlap, and hierarchical context. Non-table
    text is delegated to ParagraphChunker.
    """

    name = "sec_table"

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        er = config.get("equity_research", config)
        self.rows_per_chunk = int(er.get("table_rows_per_chunk", 12))
        self.row_overlap = int(er.get("table_row_overlap", 2))
        self.context_paragraphs = int(er.get("table_context_paragraphs", 2))
        self._paragraph = ParagraphChunker(config)

    # -- public API ---------------------------------------------------------

    def chunk(self, text: str, *, metadata: dict[str, Any]) -> list[Chunk]:
        doc_key = metadata.get("doc_key", metadata.get("accession_number", "doc"))
        lines = text.split("\n")
        table_regions = _detect_table_regions(lines)

        if not table_regions:
            # No tables found — delegate entirely to ParagraphChunker
            return self._paragraph.chunk(text, metadata=metadata)

        chunks: list[Chunk] = []
        global_idx = 0
        prev_end = -1

        for table_start, table_end in table_regions:
            # Process non-table text before this table
            if table_start > prev_end + 1:
                gap_text = "\n".join(lines[prev_end + 1 : table_start])
                if gap_text.strip():
                    gap_meta = {**metadata, "chunk_type": "text"}
                    for c in self._paragraph.chunk(gap_text, metadata=gap_meta):
                        c.chunk_id = f"{doc_key}_{global_idx}"
                        c.chunk_index = global_idx
                        global_idx += 1
                        chunks.append(c)

            # Process the table
            table_chunks = self._chunk_table(
                lines, table_start, table_end, metadata, doc_key, global_idx
            )
            for c in table_chunks:
                c.chunk_id = f"{doc_key}_{global_idx}"
                c.chunk_index = global_idx
                global_idx += 1
                chunks.append(c)

            prev_end = table_end

        # Process trailing non-table text
        if prev_end + 1 < len(lines):
            gap_text = "\n".join(lines[prev_end + 1 :])
            if gap_text.strip():
                gap_meta = {**metadata, "chunk_type": "text"}
                for c in self._paragraph.chunk(gap_text, metadata=gap_meta):
                    c.chunk_id = f"{doc_key}_{global_idx}"
                    c.chunk_index = global_idx
                    global_idx += 1
                    chunks.append(c)

        return chunks

    # -- table chunking internals -------------------------------------------

    def _chunk_table(
        self,
        lines: list[str],
        table_start: int,
        table_end: int,
        metadata: dict[str, Any],
        doc_key: str,
        start_idx: int,
    ) -> list[Chunk]:
        title, unit_note = _extract_table_title(lines, table_start)
        header_rows = _extract_header_rows(lines, table_start, table_end)
        context_paras = _extract_context_paragraphs(
            lines, table_start, table_end, self.context_paragraphs
        )
        body_rows = _split_table_body_into_rows(lines, table_start, table_end)

        if not body_rows:
            return []

        # Build context footer
        context_footer = ""
        if context_paras:
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for p in context_paras:
                if p not in seen:
                    seen.add(p)
                    unique.append(p)
            context_footer = "\n---\nContext: " + " ".join(unique)

        # Build header block
        header_block = ""
        if title:
            header_block += title + "\n"
        if unit_note:
            header_block += unit_note + "\n"
        if header_rows:
            header_block += "\n".join(header_rows) + "\n"

        # Split body_rows into sub-chunks with overlap
        sub_chunks = self._split_rows(body_rows)
        table_section = metadata.get("section", "financial_statements")

        result: list[Chunk] = []
        for sc_idx, (rows, parent_ctx) in enumerate(sub_chunks):
            parts: list[str] = []
            if sc_idx == 0:
                parts.append(header_block.rstrip())
            else:
                parts.append(f"{title}  (continued)" if title else "(continued)")
                if unit_note:
                    parts.append(unit_note)
                # Re-emit header rows
                if header_rows:
                    parts.append("\n".join(header_rows))
                # Inject parent context continuation
                if parent_ctx:
                    ctx_str = ", ".join(parent_ctx)
                    parts.append(f"[Continued from: {ctx_str}]")

            # Separator
            parts.append("─" * 60)

            # Body rows
            for raw_line, _kind, _ctx in rows:
                parts.append(raw_line)

            # Context footer
            if context_footer:
                parts.append(context_footer)

            chunk_text = "\n".join(parts)
            chunk_meta = {
                **metadata,
                "chunk_type": "table",
                "table_title": title,
                "table_section": table_section,
                "parent_labels": parent_ctx,
            }
            result.append(
                Chunk(
                    chunk_id=f"{doc_key}_{start_idx + sc_idx}",
                    text=chunk_text,
                    doc_key=doc_key,
                    chunk_index=start_idx + sc_idx,
                    metadata=chunk_meta,
                )
            )

        return result

    def _split_rows(
        self, rows: list[tuple[str, str, list[str]]]
    ) -> list[tuple[list[tuple[str, str, list[str]]], list[str]]]:
        """Split rows into sub-chunks of size rows_per_chunk with row_overlap.

        Returns list of (rows_slice, parent_context_for_continuation).
        parent_context_for_continuation is empty for the first sub-chunk.
        """
        n = len(rows)
        step = self.rows_per_chunk
        overlap = self.row_overlap
        result: list[tuple[list[tuple[str, str, list[str]]], list[str]]] = []

        i = 0
        while i < n:
            end = min(i + step, n)
            sub = rows[i:end]
            # Parent context for continuation: the parent labels of the
            # last DATA row in the previous sub-chunk (or current for first).
            parent_ctx: list[str] = []
            if result:
                # Get parent context from the last row of previous chunk
                prev_sub = result[-1][0]
                for raw, kind, ctx in reversed(prev_sub):
                    if kind == "DATA" and ctx:
                        parent_ctx = ctx
                        break
                    elif ctx:
                        parent_ctx = ctx
                        break
            result.append((sub, parent_ctx))
            if end >= n:
                break
            i = end - overlap
            if i <= (end - step):
                # Safety: prevent infinite loop if overlap >= step
                i = end

        return result
