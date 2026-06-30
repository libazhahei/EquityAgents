"""Text similarity and list deduplication helpers."""

from __future__ import annotations

from difflib import SequenceMatcher


def similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def canonical_key(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())


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
        if any(similarity(item, prev) >= threshold for prev in merged):
            continue
        merged.append(item)
    return merged
