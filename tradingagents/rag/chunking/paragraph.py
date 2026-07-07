"""Paragraph-based chunking with sentence-level splitting and overlap."""

from __future__ import annotations

import re
from typing import Any

from tradingagents.rag.types import Chunk

# Split on sentence boundaries: period followed by space + uppercase letter,
# or period followed by end of string.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"\(])")


class ParagraphChunker:
    name = "paragraph"

    def __init__(self, config: dict[str, Any] | None = None):
        config = config or {}
        er = config.get("equity_research", config)
        self.chunk_size = int(er.get("filing_chunk_size", er.get("rag_chunk_size", 300)))
        self.overlap = int(er.get("filing_chunk_overlap", er.get("rag_chunk_overlap", 100)))

    def chunk(self, text: str, *, metadata: dict[str, Any]) -> list[Chunk]:
        doc_key = metadata.get("doc_key", metadata.get("accession_number", "doc"))
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            return []

        merged: list[str] = []
        current: list[str] = []
        current_words = 0

        for para in paragraphs:
            words = para.split()
            if current_words + len(words) > self.chunk_size and current:
                merged.append("\n\n".join(current))
                # Build overlap from last N words of current block
                all_words = " ".join(current).split()
                overlap_text = " ".join(all_words[-self.overlap :]) if self.overlap else ""
                current = [overlap_text, para] if overlap_text else [para]
                current_words = len(overlap_text.split()) + len(words) if overlap_text else len(words)
            else:
                current.append(para)
                current_words += len(words)

        if current:
            merged.append("\n\n".join(current))

        # Post-process: split any merged block that exceeds chunk_size words
        final: list[str] = []
        for block in merged:
            block_words = block.split()
            if len(block_words) <= self.chunk_size:
                final.append(block)
            else:
                final.extend(self._split_oversized(block))

        chunks: list[Chunk] = []
        for idx, body in enumerate(final):
            chunk_id = f"{doc_key}_{idx}"
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=body,
                    doc_key=doc_key,
                    chunk_index=idx,
                    metadata={
                        **metadata,
                        "section": metadata.get("section", "full"),
                        "subsection_key": metadata.get("subsection_key", metadata.get("section", "full")),
                        "subsection_title": metadata.get("subsection_title", metadata.get("section", "full")),
                        "chunk_type": metadata.get("chunk_type", "text"),
                    },
                )
            )
        return chunks

    def _split_oversized(self, block: str) -> list[str]:
        """Split a block that exceeds chunk_size words into sentence-level pieces."""
        # Try sentence-level splitting first
        sentences = _SENTENCE_SPLIT_RE.split(block)
        if len(sentences) > 1:
            result: list[str] = []
            current: list[str] = []
            current_words = 0
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                sent_words = len(sent.split())
                if current_words + sent_words > self.chunk_size and current:
                    result.append(" ".join(current))
                    # Overlap: last N words
                    all_w = " ".join(current).split()
                    overlap_text = " ".join(all_w[-self.overlap :]) if self.overlap else ""
                    if overlap_text:
                        current = [overlap_text, sent]
                        current_words = len(overlap_text.split()) + sent_words
                    else:
                        current = [sent]
                        current_words = sent_words
                else:
                    current.append(sent)
                    current_words += sent_words
            if current:
                result.append(" ".join(current))
            # Check if any result is still too long (single long sentence)
            final: list[str] = []
            for piece in result:
                if len(piece.split()) > self.chunk_size:
                    final.extend(self._hard_split(piece))
                else:
                    final.append(piece)
            return final
        # Single sentence that's too long — hard split by words
        return self._hard_split(block)

    def _hard_split(self, text: str) -> list[str]:
        """Hard-split text by word count with overlap."""
        words = text.split()
        if len(words) <= self.chunk_size:
            return [text]
        
        result: list[str] = []
        i = 0
        while i < len(words):
            end = min(i + self.chunk_size, len(words))
            result.append(" ".join(words[i:end]))
            
            # If we've reached the end, we're done
            if end >= len(words):
                break
                
            # Move forward by (chunk_size - overlap), but ensure progress
            i = end - self.overlap
            # Safety: ensure we always make progress
            if i >= end:
                i = end
        
        return result
