"""Tests for in-memory ledger persistence."""

from tradingagents.equity_research.storage.in_memory import InMemoryLedgerStore, InMemoryStore
from tradingagents.equity_research.storage.ledger_store import hydrate_state_from_ledger_store


def setup_function():
    InMemoryStore.reset()


def test_ledger_store_upsert_and_load():
    store = InMemoryLedgerStore()
    entry = {
        "evidence_id": "e1",
        "quote": "revenue up",
        "created_at": "2026-01-01T00:00:00",
        "created_by": "test",
    }
    store.upsert("report-1", "AAPL", "evidence", entry, created_by="test")
    loaded = store.load_by_report("report-1")
    assert len(loaded["evidence_ledger"]) == 1
    assert loaded["evidence_ledger"][0]["evidence_id"] == "e1"


def test_hydrate_state_from_ledger_store():
    store = InMemoryLedgerStore()
    store.upsert(
        "report-2",
        "MSFT",
        "claim",
        {"claim_id": "c1", "claim": "cloud growth", "created_at": "2026-01-01T00:00:00"},
    )
    state = {"report_id": "report-2", "ticker": "MSFT", "evidence_ledger": [], "claim_ledger": []}
    updates = hydrate_state_from_ledger_store(state, store)
    assert len(updates["claim_ledger"]) == 1
