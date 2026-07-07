"""Persistent storage for research ledger entries."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.storage.db import LedgerEntryRow, get_session

_LEDGER_TYPE_TO_STATE_KEY = {
    "evidence": "evidence_ledger",
    "claim": "claim_ledger",
    "assumption": "assumption_ledger",
    "consensus": "consensus_ledger",
    "broker_view": "broker_view_ledger",
    "forecast": "forecast_ledger",
    "valuation": "valuation_ledger",
    "issue": "issue_ledger",
    "thesis": "thesis_ledger",
    "iteration_snapshot": "iteration_snapshots",
}

_ID_FIELDS = {
    "evidence": "evidence_id",
    "claim": "claim_id",
    "assumption": "assumption_id",
    "consensus": "consensus_id",
    "broker_view": "view_id",
    "forecast": "forecast_id",
    "valuation": "valuation_id",
    "issue": "issue_id",
    "thesis": "thesis_id",
    "iteration_snapshot": "snapshot_id",
}


class LedgerStore:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def upsert(
        self,
        report_id: str,
        ticker: str,
        ledger_type: str,
        entry: dict[str, Any],
        *,
        created_by: str = "",
    ) -> dict[str, Any]:
        id_field = _ID_FIELDS.get(ledger_type, "id")
        entry_id = entry.get(id_field) or entry.get("id", "")
        if not entry_id:
            return entry
        session = get_session(self.config)
        try:
            created_at_raw = entry.get("created_at", "")
            created_at = datetime.utcnow()
            if created_at_raw:
                try:
                    created_at = datetime.fromisoformat(
                        str(created_at_raw).replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except (ValueError, TypeError):
                    pass
            row = session.get(LedgerEntryRow, entry_id)
            if row is None:
                row = LedgerEntryRow(
                    entry_id=entry_id,
                    report_id=report_id,
                    ticker=ticker.upper(),
                    ledger_type=ledger_type,
                    payload=entry,
                    created_by=created_by or entry.get("created_by", ""),
                    created_at=created_at,
                )
                session.add(row)
            else:
                row.payload = entry
                row.report_id = report_id
                row.ticker = ticker.upper()
                row.ledger_type = ledger_type
                if created_by or entry.get("created_by"):
                    row.created_by = created_by or entry.get("created_by", "")
            session.commit()
            return entry
        finally:
            session.close()

    def load_by_report(self, report_id: str) -> dict[str, list[dict[str, Any]]]:
        session = get_session(self.config)
        try:
            rows = (
                session.query(LedgerEntryRow)
                .filter_by(report_id=report_id)
                .order_by(LedgerEntryRow.created_at)
                .all()
            )
            result: dict[str, list[dict[str, Any]]] = {}
            for row in rows:
                state_key = _LEDGER_TYPE_TO_STATE_KEY.get(row.ledger_type, f"{row.ledger_type}_ledger")
                result.setdefault(state_key, []).append(dict(row.payload or {}))
            return result
        finally:
            session.close()

    def list_by_ticker(
        self,
        ticker: str,
        ledger_type: str | None = None,
    ) -> list[dict[str, Any]]:
        session = get_session(self.config)
        try:
            query = session.query(LedgerEntryRow).filter_by(ticker=ticker.upper())
            if ledger_type:
                query = query.filter_by(ledger_type=ledger_type)
            rows = query.order_by(LedgerEntryRow.created_at.desc()).all()
            return [dict(row.payload or {}) for row in rows]
        finally:
            session.close()


def hydrate_state_from_ledger_store(
    state: dict[str, Any],
    ledger_store: Any,
) -> dict[str, Any]:
    """Load persisted ledgers into state when report_id is set and ledgers are empty."""
    report_id = state.get("report_id", "")
    if not report_id:
        return {}
    if state.get("evidence_ledger") or state.get("claim_ledger"):
        return {}
    loaded = ledger_store.load_by_report(report_id)
    if not loaded:
        return {}
    updates: dict[str, Any] = {}
    for key, entries in loaded.items():
        if entries:
            updates[key] = entries
    return updates
