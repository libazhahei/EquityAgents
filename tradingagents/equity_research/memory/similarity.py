"""Text and vector similarity helpers for memory retrieval."""

from __future__ import annotations

import math


def _text_similarity(query: str, text: str) -> float:
    """Asymmetric query→text token overlap for memory retrieval scoring."""
    if not query or not text:
        return 0.0
    q_tokens = set(query.lower().split())
    t_tokens = set(text.lower().split())
    if not q_tokens:
        return 0.0
    return len(q_tokens & t_tokens) / len(q_tokens)


def text_similarity(a: str, b: str) -> float:
    """Symmetric Jaccard token overlap for deduplication (no embedding required)."""
    if not a or not b:
        return 0.0
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    union = a_tokens | b_tokens
    if not union:
        return 0.0
    return len(a_tokens & b_tokens) / len(union)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)
