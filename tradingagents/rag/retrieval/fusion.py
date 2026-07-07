"""Rank fusion strategies."""

from __future__ import annotations


class RRFFusion:
    def __init__(self, k: int = 60):
        self.default_k = k

    def fuse(
        self,
        rankings: list[list[tuple[str, float]]],
        *,
        k: int | None = None,
    ) -> list[tuple[str, float]]:
        k = k if k is not None else self.default_k
        scores: dict[str, float] = {}
        for ranking in rankings:
            for rank, (chunk_id, _raw) in enumerate(ranking, start=1):
                scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
        return sorted(scores.items(), key=lambda x: x[1], reverse=True)
