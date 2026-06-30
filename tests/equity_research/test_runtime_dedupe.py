"""Tests for runtime deduplication helpers."""

from tradingagents.equity_research.runtime.utils.dedupe import (
    canonical_key,
    find_similar_index,
    merge_list_by_similarity,
    similarity,
)


def test_canonical_key_normalizes_punctuation():
    a = "Track Blackwell ramp and margin bridge"
    b = "Track Blackwell ramp and margin-bridge"
    assert canonical_key(a) == canonical_key(b)


def test_merge_list_dedupes_similar_strings():
    result = merge_list_by_similarity(
        ["Track Blackwell ramp and margin bridge"],
        ["Track Blackwell ramp and gross margin bridge"],
    )
    assert len(result) == 1
    assert "gross" in result[0]


def test_merge_list_preserves_distinct_strings():
    result = merge_list_by_similarity(
        ["Hyperscaler capex outlook"],
        ["Custom ASIC competition risk"],
    )
    assert len(result) == 2


def test_find_similar_index_matches_canonical_key():
    items = ["Track Blackwell ramp and margin bridge"]
    idx = find_similar_index(items, "Track Blackwell ramp and margin-bridge")
    assert idx == 0


def test_similarity_delegates_to_text_similarity():
    assert similarity("alpha beta", "beta alpha") == 1.0
