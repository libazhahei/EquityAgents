"""Tests for ledger sync helpers."""

from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy, write_to_ledger


def test_sync_ledgers_from_legacy_claims():
    state = {
        "claims": [{
            "claim_id": "c1",
            "section_id": "3_business_model",
            "text": "Revenue grows via cloud",
            "claim_type": "driver_claim",
            "status": "verified",
        }],
        "evidence_fragments": [{
            "fragment_id": "e1",
            "text": "Cloud revenue up 28%",
            "doc_id": "d1",
        }],
        "model_assumptions": [{
            "metric": "revenue_growth",
            "our_assumption": "15%",
        }],
        "consensus_view": {
            "ticker": "TEST",
            "summary": "consensus growth 10%",
            "narrative_framework": {"bull_case": "growth"},
        },
        "broker_views": [{"view_id": "bv1", "summary": "buy rated"}],
    }
    synced = sync_ledgers_from_legacy(state)
    assert len(synced["claim_ledger"]) == 1
    assert len(synced["evidence_ledger"]) == 1
    assert len(synced["assumption_ledger"]) == 1
    assert len(synced["consensus_ledger"]) >= 1
    assert len(synced["broker_view_ledger"]) == 1


def test_sync_ledgers_legacy_list_consensus():
    state = {
        "consensus_view": [{"summary": "legacy consensus 8% growth"}],
    }
    synced = sync_ledgers_from_legacy(state)
    assert len(synced["consensus_ledger"]) == 1


def test_write_to_ledger():
    state = {"issue_ledger": []}
    updated = write_to_ledger(state, "issue", {
        "issue_id": "iss_1",
        "gate": "test",
        "message": "test issue",
    })
    assert len(updated["issue_ledger"]) == 1

