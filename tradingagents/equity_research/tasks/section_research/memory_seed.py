"""Seed parent consensus/assumption into section research subgraph ledgers."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.state.consensus_schemas import StructuredConsensusView
from tradingagents.equity_research.state.ledgers import (
    AssumptionLedgerEntry,
    assumption_dict_to_ledger_entry,
    sync_ledgers_from_legacy,
    write_to_ledger,
)


def assumption_view_to_ledger_entries(assumption_view: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    items = assumption_view.get("assumption_map") or assumption_view.get("assumptions") or []
    if not isinstance(items, list):
        return entries
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            entry = assumption_dict_to_ledger_entry(str(item))
        else:
            entry = AssumptionLedgerEntry(
                assumption_id=item.get("id") or item.get("assumption_id") or f"asm_{uuid.uuid4().hex[:8]}",
                metric=item.get("category") or item.get("metric", ""),
                our_assumption=item.get("statement", ""),
                consensus=item.get("consensus_anchor", ""),
                rationale="; ".join(item.get("evidence_for", [])[:2]),
                sensitivity=item.get("model_sensitivity", "medium"),
            ).model_dump()
        entries.append(entry)
    return entries


def seed_parent_memory_into_subgraph(parent: dict[str, Any]) -> dict[str, Any]:
    """Copy parent ledgers and materialize consensus/assumption views into ledgers."""
    state = {
        "consensus_ledger": list(parent.get("consensus_ledger") or []),
        "assumption_ledger": list(parent.get("assumption_ledger") or []),
        "evidence_ledger": list(parent.get("evidence_ledger") or []),
        "claim_ledger": list(parent.get("claim_ledger") or []),
        "memory_reflections": list(parent.get("memory_reflections") or []),
        "iteration_snapshots": list(parent.get("iteration_snapshots") or []),
        "memory_conflicts": list(parent.get("memory_conflicts") or []),
        "consensus_view": parent.get("consensus_view") or {},
        "assumption_view": parent.get("assumption_view") or {},
        "model_assumptions": list(parent.get("model_assumptions") or []),
        "evidence_fragments": list(parent.get("evidence_fragments") or []),
        "claims": list(parent.get("claims") or []),
    }

    consensus_view = parent.get("consensus_view")
    if isinstance(consensus_view, dict) and consensus_view:
        try:
            entries = StructuredConsensusView.model_validate(consensus_view).to_ledger_entries()
        except Exception:
            entries = [{
                "consensus_id": f"cons_{parent.get('ticker', 'x')}_overall",
                "metric": "overall",
                "consensus_value": str(consensus_view.get("summary", ""))[:500],
                "source": "parent_state",
            }]
        for entry in entries:
            state.update(write_to_ledger(state, "consensus", entry))

    assumption_view = parent.get("assumption_view")
    if isinstance(assumption_view, dict) and assumption_view:
        for entry in assumption_view_to_ledger_entries(assumption_view):
            state.update(write_to_ledger(state, "assumption", entry))

    return sync_ledgers_from_legacy(state)


def merge_subgraph_ledgers_to_parent(
    parent: dict[str, Any],
    subgraph_result: dict[str, Any],
) -> dict[str, Any]:
    """Merge append-only ledger updates from subgraph back to parent."""
    updates: dict[str, Any] = {}
    ledger_keys = (
        "consensus_ledger",
        "assumption_ledger",
        "evidence_ledger",
        "claim_ledger",
        "memory_reflections",
        "iteration_snapshots",
        "memory_conflicts",
    )
    for key in ledger_keys:
        parent_ledger = list(parent.get(key) or [])
        subgraph_ledger = list(subgraph_result.get(key) or [])
        if not subgraph_ledger:
            continue
        id_fields = {
            "consensus_ledger": "consensus_id",
            "assumption_ledger": "assumption_id",
            "evidence_ledger": "evidence_id",
            "claim_ledger": "claim_id",
            "memory_reflections": "reflection_id",
            "iteration_snapshots": "snapshot_id",
            "memory_conflicts": "conflict_id",
        }
        id_field = id_fields.get(key, "id")
        existing = {e.get(id_field) for e in parent_ledger}
        merged = list(parent_ledger)
        for entry in subgraph_ledger:
            eid = entry.get(id_field)
            if eid and eid in existing:
                continue
            merged.append(entry)
            if eid:
                existing.add(eid)
        updates[key] = merged
    return updates
