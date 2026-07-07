"""Tests for iteration memory snapshots."""

from tradingagents.equity_research.memory.snapshots import capture_iteration_snapshot
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.equity_research.storage.in_memory import InMemoryLedgerStore


def test_capture_iteration_snapshot():
    state = empty_equity_research_state()
    state["research_iterations"] = 2
    state["consensus_ledger"] = [{"consensus_id": "c1", "metric": "eps", "consensus_value": "5.0"}]
    state["assumption_ledger"] = [
        {"assumption_id": "a1", "metric": "margin", "sensitivity": "high"},
        {"assumption_id": "a2", "metric": "growth", "sensitivity": "low"},
    ]
    state["valuation_ledger"] = [{"valuation_id": "v1", "target_price": 200.0}]
    state["evidence_ledger"] = [{"evidence_id": "e1", "status": "active"}]
    state["claim_ledger"] = [{"claim_id": "cl1"}]
    state["memory_conflicts"] = [{"conflict_id": "x1"}]

    deps = type("Deps", (), {"ledgers": InMemoryLedgerStore()})()
    updates = capture_iteration_snapshot(state, deps=deps)
    snap = updates["iteration_snapshots"][0]
    assert snap["research_iteration"] == 2
    assert len(snap["consensus_summary"]) == 1
    assert len(snap["key_assumptions"]) == 1
    assert snap["valuation_snapshot"]["target_price"] == 200.0
    assert snap["open_conflicts"] == 1
