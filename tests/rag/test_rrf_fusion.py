"""Tests for RRF fusion."""

from tradingagents.rag.retrieval.fusion import RRFFusion


def test_rrf_fusion_merges_rankings():
    fusion = RRFFusion(k=60)
    lexical = [("a", 1.0), ("b", 0.5), ("c", 0.3)]
    vector = [("b", 0.9), ("d", 0.8), ("a", 0.4)]
    fused = fusion.fuse([lexical, vector])
    ids = [item[0] for item in fused]
    assert "a" in ids and "b" in ids
    assert ids[0] in {"a", "b"}
