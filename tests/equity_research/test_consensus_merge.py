"""Tests for consensus view merge and semantic deduplication."""

from tradingagents.equity_research.state.consensus_schemas import (
    ConsensusViewUpdate,
    NarrativeFramework,
    empty_structured_consensus_view,
)
from tradingagents.equity_research.tasks.consensus.merge import merge_view_update


def test_merge_key_debates_semantic_dedupe():
    view = empty_structured_consensus_view("NVDA")
    view.narrative_framework.key_debates = ["Track Blackwell ramp and margin bridge"]
    update = ConsensusViewUpdate(
        narrative_framework=NarrativeFramework(
            key_debates=["Track Blackwell ramp and gross margin bridge"],
        ),
    )
    merged = merge_view_update(view, update)
    assert len(merged.narrative_framework.key_debates) == 1
    assert "gross" in merged.narrative_framework.key_debates[0]


def test_merge_sources_exact_dedupe_only():
    view = empty_structured_consensus_view("NVDA")
    view.narrative_framework.sources = ["https://example.com/a"]
    update = ConsensusViewUpdate(
        narrative_framework=NarrativeFramework(
            sources=["https://example.com/a", "https://example.com/b"],
        ),
    )
    merged = merge_view_update(view, update)
    assert merged.narrative_framework.sources == [
        "https://example.com/a",
        "https://example.com/b",
    ]
