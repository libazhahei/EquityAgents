"""Tests for orthogonal memory search tools."""

from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.equity_research.tools import memory_search_tools


def test_search_evidence_by_metric():
    state = empty_equity_research_state()
    state["evidence_ledger"] = [
        {"evidence_id": "e1", "quote": "revenue grew 20%", "metric": "revenue", "status": "active"},
        {"evidence_id": "e2", "quote": "margin expanded", "metric": "margin", "status": "active"},
    ]
    result = memory_search_tools.search_evidence(state, "revenue", metric="revenue")
    assert result["tool"] == "search_evidence"
    assert result["count"] == 1
    assert result["items"][0]["evidence_id"] == "e1"


def test_search_claims_by_section_and_confidence():
    state = empty_equity_research_state()
    state["claim_ledger"] = [
        {"claim_id": "c1", "claim": "revenue up", "section_id": "s1", "confidence": 0.9},
        {"claim_id": "c2", "claim": "margin flat", "section_id": "s2", "confidence": 0.3},
    ]
    result = memory_search_tools.search_claims(
        state, section_id="s1", confidence_min=0.5,
    )
    assert result["count"] == 1
    assert result["items"][0]["claim_id"] == "c1"


def test_search_assumptions_high_sensitivity():
    state = empty_equity_research_state()
    state["assumption_ledger"] = [
        {"assumption_id": "a1", "metric": "margin", "sensitivity": "high"},
        {"assumption_id": "a2", "metric": "growth", "sensitivity": "low"},
    ]
    result = memory_search_tools.search_assumptions(state, sensitivity="high")
    assert result["count"] == 1
    assert result["items"][0]["assumption_id"] == "a1"


def test_search_conflicts():
    state = empty_equity_research_state()
    state["memory_conflicts"] = [{"conflict_id": "x1", "metric": "revenue"}]
    state["contradiction_fragments"] = [{"fragment_id": "e1", "metric": "revenue"}]
    result = memory_search_tools.search_conflicts(state, metric="revenue")
    assert result["open_conflicts"] == 1
    assert len(result["contradiction_fragments"]) == 1


def test_search_memory_timeline():
    state = empty_equity_research_state()
    state["iteration_snapshots"] = [
        {"snapshot_id": "s1", "research_iteration": 1},
        {"snapshot_id": "s2", "research_iteration": 2},
    ]
    result = memory_search_tools.search_memory_timeline(state, last_n=1)
    assert result["count"] == 1
    assert result["snapshots"][0]["snapshot_id"] == "s2"


def test_search_research_context_bundle():
    state = empty_equity_research_state()
    state["evidence_ledger"] = [{"evidence_id": "e1", "quote": "growth", "status": "active"}]
    state["claim_ledger"] = [{"claim_id": "c1", "claim": "growth continues"}]
    result = memory_search_tools.search_research_context(state, "growth")
    assert result["tool"] == "search_research_context"
    assert result.get("evidence") or result.get("claims")
