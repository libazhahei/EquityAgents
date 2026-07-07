"""Chunking strategies."""

from tradingagents.rag.chunking.fixed import FixedSizeChunker
from tradingagents.rag.chunking.paragraph import ParagraphChunker
from tradingagents.rag.chunking.passthrough import PassthroughChunker
from tradingagents.rag.chunking.sec_item import SecItemChunker
from tradingagents.rag.chunking.sec_table import SecTableChunker

CHUNKERS: dict[str, type] = {
    "paragraph": ParagraphChunker,
    "fixed": FixedSizeChunker,
    "sec_item": SecItemChunker,
    "sec_table": SecTableChunker,
    "passthrough": PassthroughChunker,
}


def get_chunker(name: str, config: dict | None = None) -> object:
    cls = CHUNKERS.get(name, ParagraphChunker)
    return cls(config or {})


__all__ = [
    "CHUNKERS",
    "FixedSizeChunker",
    "ParagraphChunker",
    "PassthroughChunker",
    "SecItemChunker",
    "SecTableChunker",
    "get_chunker",
]
