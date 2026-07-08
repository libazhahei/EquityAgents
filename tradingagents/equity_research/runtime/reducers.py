"""LangGraph-compatible reducer functions for equity research state channels.

Each reducer merges new items into the existing list with the strategy
appropriate for that channel — semantic dedup for evidence, doc_id dedup
for documents, and simple append for facts/calculations.
"""

from __future__ import annotations

from tradingagents.equity_research.memory.similarity import text_similarity

# Threshold for semantic deduplication of evidence snippets.
_DEDUP_THRESHOLD = 0.85


def evidence_buffer_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append new evidence with semantic deduplication (Jaccard overlap)."""
    if not new:
        return existing
    merged = list(existing)
    for item in new:
        snippet = item.get("snippet", "")
        is_dup = any(
            text_similarity(snippet, e.get("snippet", "")) >= _DEDUP_THRESHOLD
            for e in existing
        )
        if not is_dup:
            merged.append(item)
    return merged


def pending_evidence_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append — the synthesizer drains this channel; the apply node clears it."""
    return existing + new


def documents_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append documents, deduplicating by ``doc_id``."""
    seen = {d.get("doc_id") for d in existing if d.get("doc_id")}
    merged = list(existing)
    for item in new:
        doc_id = item.get("doc_id")
        if doc_id and doc_id not in seen:
            merged.append(item)
            seen.add(doc_id)
        elif not doc_id:
            merged.append(item)
    return merged


def errors_reducer(existing: list[str], new: list[str]) -> list[str]:
    """Append error messages."""
    return existing + new


def fact_store_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append fact-store entries."""
    return existing + new


def calculation_store_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append calculation-store entries."""
    return existing + new
