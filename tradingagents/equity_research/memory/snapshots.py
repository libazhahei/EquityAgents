"""Iteration-level memory snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class IterationSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"snap_{uuid.uuid4().hex[:8]}")
    research_iteration: int = 0
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    consensus_summary: list[dict] = Field(default_factory=list)
    key_assumptions: list[dict] = Field(default_factory=list)
    valuation_snapshot: dict | None = None
    evidence_count: int = 0
    claim_count: int = 0
    open_conflicts: int = 0


def capture_iteration_snapshot(state: dict[str, Any], deps: Any = None) -> dict[str, Any]:
    consensus = list(state.get("consensus_ledger", []))[:3]
    key_assumptions = [
        a for a in state.get("assumption_ledger", [])
        if str(a.get("sensitivity", "")).lower() == "high"
    ]
    valuation_entries = state.get("valuation_ledger", [])
    valuation_snapshot = valuation_entries[-1] if valuation_entries else None
    snapshot = IterationSnapshot(
        research_iteration=int(state.get("research_iterations", 0)),
        consensus_summary=consensus,
        key_assumptions=key_assumptions,
        valuation_snapshot=valuation_snapshot,
        evidence_count=len([
            e for e in state.get("evidence_ledger", [])
            if e.get("status", "active") == "active"
        ]),
        claim_count=len(state.get("claim_ledger", [])),
        open_conflicts=len(state.get("memory_conflicts", [])),
    )
    payload = snapshot.model_dump()
    snapshots = list(state.get("iteration_snapshots", []))
    snapshots.append(payload)
    updates: dict[str, Any] = {"iteration_snapshots": snapshots}
    if deps is not None and hasattr(deps, "ledgers"):
        deps.ledgers.upsert(
            state.get("report_id", ""),
            state.get("ticker", ""),
            "iteration_snapshot",
            payload,
            created_by="research_loop",
        )
    return updates
