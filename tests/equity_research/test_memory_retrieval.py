"""Tests for collaborative memory retrieval."""

from tradingagents.equity_research.memory.retrieval import build_memory_context, memory_score
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


def test_memory_score_weights():
    score = memory_score(
        semantic_similarity=1.0,
        evidence_reliability=1.0,
        thesis_node_score=1.0,
        recency_score=1.0,
        financial_materiality=1.0,
        redundancy_penalty=0.0,
    )
    assert score > 0.9


def test_build_memory_context_samples_ledgers():
    state = empty_equity_research_state()
    state["evidence_ledger"] = [{
        "evidence_id": "e1",
        "quote": "revenue growth accelerated",
        "reliability_score": 0.8,
    }]
    state["claim_ledger"] = [{
        "claim_id": "c1",
        "claim": "revenue growth will continue",
        "confidence": 0.7,
        "is_core_thesis": True,
    }]
    ctx = build_memory_context(state, [], {"priority_questions": ["revenue growth"]})
    assert ctx["query"]
    assert len(ctx["evidence"]) >= 1
    assert len(ctx["claims"]) >= 1
