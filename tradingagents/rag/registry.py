"""Corpus registry."""

from __future__ import annotations

from tradingagents.rag.corpora.base import CorpusDefinition


class CorpusRegistry:
    def __init__(self):
        self._corpora: dict[str, CorpusDefinition] = {}

    def register(self, definition: CorpusDefinition) -> None:
        self._corpora[definition.corpus_id] = definition

    def get(self, corpus_id: str) -> CorpusDefinition:
        if corpus_id not in self._corpora:
            raise KeyError(f"Unknown corpus: {corpus_id}")
        return self._corpora[corpus_id]

    def list_ids(self) -> list[str]:
        return list(self._corpora.keys())
