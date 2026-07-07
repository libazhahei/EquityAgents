"""Tests for rule-based memory conflict detection."""

from tradingagents.equity_research.memory.conflict import (
    apply_conflicts_to_state,
    detect_conflicts,
)
from tradingagents.equity_research.tools.evidence_memory import store_evidence


def test_detect_conflicts_on_opposing_metrics():
    new_entry = {
        "evidence_id": "e2",
        "metric": "revenue_growth",
        "value": "-5%",
        "direction": "down",
        "reliability_score": 0.6,
    }
    existing = [{
        "evidence_id": "e1",
        "metric": "revenue growth",
        "value": "+15%",
        "direction": "up",
        "reliability_score": 0.7,
        "status": "active",
    }]
    conflicts = detect_conflicts(new_entry, existing)
    assert len(conflicts) == 1
    assert conflicts[0]["metric"] == "revenue_growth"


def test_apply_conflicts_downgrades_linked_claim():
    state = {
        "evidence_ledger": [{
            "evidence_id": "e1",
            "metric": "margin",
            "value": "20%",
            "status": "active",
            "contradicting_evidence": [],
            "reliability_score": 0.5,
        }],
        "claims": [{
            "claim_id": "c1",
            "supporting_evidence_ids": ["e1", "e2"],
            "confidence": 0.8,
        }],
        "claim_ledger": [{
            "claim_id": "c1",
            "supporting_evidence": ["e1", "e2"],
            "confidence": 0.8,
        }],
        "contradiction_fragments": [],
        "memory_conflicts": [],
    }
    new_entry = {
        "evidence_id": "e2",
        "metric": "margin",
        "value": "-5%",
        "reliability_score": 0.9,
        "contradicting_evidence": [],
    }
    conflicts = detect_conflicts(new_entry, state["evidence_ledger"])
    updates = apply_conflicts_to_state(state, new_entry, conflicts)
    assert updates["claims"][0]["confidence"] < 0.8
    assert updates["memory_conflicts"]


def test_store_evidence_records_provenance_fields():
    state = {"ticker": "AAPL", "report_id": "r1", "evidence_ledger": [], "evidence_fragments": []}
    result = store_evidence(
        state,
        {"text": "Services revenue grew", "metric": "services_revenue", "created_by": "test"},
        created_by="test",
    )
    entry = result["evidence_ledger"][0]
    assert entry.get("fragment_id") == entry.get("evidence_id")
    assert entry.get("created_by") == "test"
    assert entry.get("created_at")
