"""Tests for collaborative memory retrieval."""

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.memory.retrieval import (
    build_memory_context,
    memory_score,
    text_similarity,
)
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.equity_research.storage.in_memory import InMemoryStore


def setup_function():
    InMemoryStore.reset()


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


def test_text_similarity_symmetric():
    assert text_similarity("hello world", "world hello") == 1.0
    assert text_similarity("", "hello") == 0.0


def test_text_similarity_similar_phrases():
    a = "Track Blackwell ramp and margin bridge"
    b = "Track Blackwell ramp and gross margin bridge"
    assert text_similarity(a, b) >= 0.85


def test_build_memory_context_with_filters():
    state = empty_equity_research_state()
    state["claim_ledger"] = [
        {"claim_id": "c1", "claim": "revenue growth", "confidence": 0.9, "section_id": "s1"},
        {"claim_id": "c2", "claim": "margin stable", "confidence": 0.3, "section_id": "s2"},
    ]
    ctx = build_memory_context(
        state,
        [],
        {"priority_questions": ["revenue"]},
        filters={"confidence_min": 0.5, "section_id": "s1"},
    )
    assert len(ctx["claims"]) == 1
    assert ctx["claims"][0]["claim_id"] == "c1"


def test_build_memory_context_embedding_fallback():
    config = DEFAULT_CONFIG.copy()
    config["equity_research_use_memory"] = True
    config["equity_research"] = {
        **config.get("equity_research", {}),
        "memory_use_embedding": True,
    }
    deps = EquityResearchDeps(config=config, deep_llm=None, quick_llm=None, nano_llm=None)
    state = empty_equity_research_state()
    state["ticker"] = "NVDA"
    state["evidence_ledger"] = [{
        "evidence_id": "e1",
        "fragment_id": "e1",
        "quote": "data center revenue expansion",
        "reliability_score": 0.8,
    }]
    deps.evidence.insert(
        ticker="NVDA",
        doc_id="d1",
        excerpt_text="data center revenue expansion",
        fragment_id="e1",
        embedding=deps.embeddings.embed("data center revenue expansion"),
    )
    ctx = build_memory_context(
        state,
        [],
        {"priority_questions": ["data center sales"]},
        deps=deps,
    )
    assert ctx["evidence"]
