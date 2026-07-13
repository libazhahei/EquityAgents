"""LangGraph-compatible reducer functions for equity research state channels.

Session list channels use keyed-merge (first-seen wins) so full-list resubmits
from executor nodes do not exponentially double. Narrative text channels also
apply Jaccard near-dup (``text_similarity`` >= 0.85). ``pending_evidence`` is
overwrite so synthesizer can drain with ``[]``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tradingagents.equity_research.memory.similarity import text_similarity

# Threshold for semantic near-duplication (evidence_buffer / fact_store / blackboard).
_DEDUP_THRESHOLD = 0.85


def _merge_by_key(
    existing: list[Any],
    new: list[Any],
    key_fn: Callable[[Any], str],
) -> list[Any]:
    """Append items from ``new`` whose key is not already present (first-seen wins)."""
    merged = list(existing)
    seen = {key_fn(item) for item in existing}
    seen.discard("")
    for item in new:
        key = key_fn(item)
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        merged.append(item)
    return merged


def _jaccard_dup(text: str, candidates: list[str], *, threshold: float = _DEDUP_THRESHOLD) -> bool:
    if not text:
        return False
    return any(text_similarity(text, other) >= threshold for other in candidates if other)


def merge_ledger_by_id(
    existing: list[dict],
    incoming: list[dict],
    id_field: str,
) -> list[dict]:
    """Upsert ledger rows by id. Never concatenate a full tool ledger onto state."""
    if not incoming:
        return list(existing)
    result = list(existing)
    index = {
        str(row.get(id_field)): i
        for i, row in enumerate(result)
        if row.get(id_field)
    }
    for row in incoming:
        if not isinstance(row, dict):
            continue
        eid = str(row.get(id_field) or "")
        if eid and eid in index:
            result[index[eid]] = row
        elif eid:
            index[eid] = len(result)
            result.append(row)
        else:
            result.append(row)
    return result


def evidence_buffer_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge evidence with evidence_id exact skip, then Jaccard on snippet."""
    if not new:
        return existing
    merged = list(existing)
    seen_ids = {str(e.get("evidence_id") or "") for e in merged}
    seen_ids.discard("")
    for item in new:
        eid = str(item.get("evidence_id") or "")
        if eid and eid in seen_ids:
            continue
        snippet = str(item.get("snippet") or item.get("content") or "")
        if _jaccard_dup(snippet, [str(e.get("snippet") or e.get("content") or "") for e in merged]):
            continue
        if eid:
            seen_ids.add(eid)
        merged.append(item)
    return merged


def pending_evidence_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Overwrite — nodes own the full pending list; synthesizer clears with ``[]``.

    Writers (executor apply/dispatch) always return the complete desired list,
    not a delta. Append semantics would double the channel each turn and make
    ``pending_evidence: []`` unable to drain.
    """
    return new


def documents_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append documents, deduplicating by ``doc_id`` or ``title|url`` fallback."""
    if not new:
        return existing

    def _doc_key(d: dict) -> str:
        doc_id = str(d.get("doc_id") or "")
        if doc_id:
            return f"id:{doc_id}"
        title = str(d.get("title") or "")
        url = str(d.get("url") or "")
        if title or url:
            return f"meta:{title}|{url}"
        return ""

    merged = list(existing)
    seen = {_doc_key(d) for d in merged}
    seen.discard("")
    for item in new:
        key = _doc_key(item)
        if not key:
            continue  # anonymous empty docs — drop
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def errors_reducer(existing: list[str], new: list[str]) -> list[str]:
    """Merge error strings by exact text (first-seen wins)."""
    return _merge_by_key(existing, new, key_fn=lambda e: str(e))


def fact_store_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge facts by evidence_id / question+text prefix, then Jaccard on text."""
    if not new:
        return existing

    def _fact_key(item: dict) -> str:
        eid = str(item.get("evidence_id") or "")
        if eid:
            return f"id:{eid}"
        qid = str(item.get("question_id") or "")
        text = str(item.get("text") or "")[:80]
        if text:
            return f"t:{qid}:{text}"
        return ""

    merged = list(existing)
    seen = {_fact_key(item) for item in merged}
    seen.discard("")
    for item in new:
        key = _fact_key(item)
        if key and key in seen:
            continue
        text = str(item.get("text") or "")
        if _jaccard_dup(text, [str(e.get("text") or "") for e in merged]):
            continue
        if key:
            seen.add(key)
        merged.append(item)
    return merged


def calculation_store_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge calculations by question_id + expression + metric (first-seen)."""

    def _calc_key(item: dict) -> str:
        return (
            f"{item.get('question_id', '')}:"
            f"{item.get('expression', '')}:"
            f"{item.get('metric', '')}"
        )

    return _merge_by_key(existing, new, key_fn=_calc_key)


def search_memory_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Merge search records by record_id or query|dimension|mode (first-seen)."""

    def _search_key(item: dict) -> str:
        rid = str(item.get("record_id") or "")
        if rid:
            return f"id:{rid}"
        return (
            f"{item.get('query', '')}|"
            f"{item.get('target_dimension', '')}|"
            f"{item.get('mode', '')}"
        )

    return _merge_by_key(existing, new, key_fn=_search_key)
