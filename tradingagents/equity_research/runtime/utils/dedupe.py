"""Text similarity and list deduplication helpers."""

from __future__ import annotations

from tradingagents.equity_research.memory.retrieval import text_similarity


def similarity(a: str, b: str) -> float:
    return text_similarity(a, b)


def canonical_key(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


def find_similar_index(
    items: list[str],
    candidate: str,
    *,
    threshold: float = 0.85,
) -> int | None:
    candidate_key = canonical_key(candidate)
    for idx, item in enumerate(items):
        if not item:
            continue
        if candidate_key and candidate_key == canonical_key(item):
            return idx
        if similarity(candidate, item) >= threshold:
            return idx
    return None


def merge_list_by_similarity(
    existing: list[str],
    new_items: list[str],
    *,
    threshold: float = 0.85,
) -> list[str]:
    merged = list(existing)
    for item in new_items:
        if not item:
            continue
        match_idx = find_similar_index(merged, item, threshold=threshold)
        if match_idx is None:
            merged.append(item)
            continue
        if len(item) > len(merged[match_idx]):
            merged[match_idx] = item
    return merged
