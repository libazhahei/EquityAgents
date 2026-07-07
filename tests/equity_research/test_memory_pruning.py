"""Tests for memory pruning and maintenance."""

from datetime import datetime, timedelta

from tradingagents.equity_research.memory.pruning import (
    decay_claim_confidence,
    merge_similar_evidence,
    prune_stale_evidence,
    run_memory_maintenance,
)
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


def test_merge_similar_evidence_keeps_higher_reliability():
    state = empty_equity_research_state()
    state["evidence_ledger"] = [
        {"evidence_id": "e1", "quote": "revenue growth accelerated in Q2", "reliability_score": 0.6},
        {"evidence_id": "e2", "quote": "revenue growth accelerated in Q2", "reliability_score": 0.9},
    ]
    result = merge_similar_evidence(state, threshold=0.85)
    ledger = result["evidence_ledger"]
    active = [e for e in ledger if e.get("status", "active") == "active"]
    merged = [e for e in ledger if e.get("status") == "merged"]
    assert len(active) == 1
    assert active[0]["evidence_id"] == "e2"
    assert merged


def test_prune_stale_unreferenced_evidence():
    old = (datetime.utcnow() - timedelta(days=40)).isoformat()
    state = empty_equity_research_state()
    state["evidence_ledger"] = [
        {"evidence_id": "e1", "quote": "old fact", "created_at": old, "status": "active"},
        {"evidence_id": "e2", "quote": "recent", "created_at": datetime.utcnow().isoformat(), "status": "active"},
    ]
    result = prune_stale_evidence(state, max_age_days=30)
    statuses = {e["evidence_id"]: e.get("status") for e in result["evidence_ledger"]}
    assert statuses["e1"] == "archived"
    assert statuses["e2"] == "active"


def test_decay_claim_confidence():
    old = (datetime.utcnow() - timedelta(days=10)).isoformat()
    state = empty_equity_research_state()
    state["claim_ledger"] = [{
        "claim_id": "c1",
        "claim": "margin expands",
        "confidence": 0.8,
        "created_at": old,
        "is_core_thesis": False,
    }]
    result = decay_claim_confidence(state, decay_rate=0.9, floor=0.1)
    assert result["claim_ledger"][0]["confidence"] < 0.8


def test_run_memory_maintenance_composes():
    state = empty_equity_research_state()
    state["evidence_ledger"] = [
        {"evidence_id": "e1", "quote": "same quote text", "reliability_score": 0.5},
        {"evidence_id": "e2", "quote": "same quote text", "reliability_score": 0.8},
    ]
    updates = run_memory_maintenance(state, deps=None)
    assert "evidence_ledger" in updates
