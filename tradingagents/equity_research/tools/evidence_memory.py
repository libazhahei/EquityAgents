"""Evidence and memory tools for equity research ledgers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.state.ledgers import (
    assumption_dict_to_ledger_entry,
    claim_dict_to_ledger_entry,
    fragment_to_evidence_entry,
)


def store_evidence(state: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    entry = fragment_to_evidence_entry(fragment)
    if not entry.get("evidence_id"):
        entry["evidence_id"] = f"evid_{uuid.uuid4().hex[:8]}"
    fragments = list(state.get("evidence_fragments", []))
    fragments.append({**fragment, "fragment_id": entry["evidence_id"]})
    ledger = list(state.get("evidence_ledger", []))
    ledger.append(entry)
    return {"evidence_fragments": fragments, "evidence_ledger": ledger, "evidence_id": entry["evidence_id"]}


def store_claim(state: dict[str, Any], claim: dict[str, Any]) -> dict[str, Any]:
    if not claim.get("claim_id"):
        claim["claim_id"] = f"clm_{uuid.uuid4().hex[:8]}"
    claims = list(state.get("claims", []))
    claims.append(claim)
    ledger = list(state.get("claim_ledger", []))
    ledger.append(claim_dict_to_ledger_entry(claim))
    return {"claims": claims, "claim_ledger": ledger, "claim_id": claim["claim_id"]}


def store_assumption(state: dict[str, Any], assumption: dict[str, Any]) -> dict[str, Any]:
    entry = assumption_dict_to_ledger_entry(assumption)
    if not entry.get("assumption_id"):
        entry["assumption_id"] = f"asm_{uuid.uuid4().hex[:8]}"
    assumptions = list(state.get("model_assumptions", []))
    assumptions.append(entry)
    ledger = list(state.get("assumption_ledger", []))
    ledger.append(entry)
    return {
        "model_assumptions": assumptions,
        "assumption_ledger": ledger,
        "assumption_id": entry["assumption_id"],
    }


def link_evidence_to_claim(
    state: dict[str, Any],
    claim_id: str,
    evidence_id: str,
) -> dict[str, Any]:
    claims = []
    for claim in state.get("claims", []):
        if claim.get("claim_id") == claim_id:
            ids = list(claim.get("supporting_evidence_ids", []))
            if evidence_id not in ids:
                ids.append(evidence_id)
            claim = {**claim, "supporting_evidence_ids": ids}
        claims.append(claim)
    ledger = []
    for entry in state.get("claim_ledger", []):
        if entry.get("claim_id") == claim_id:
            ids = list(entry.get("supporting_evidence", []))
            if evidence_id not in ids:
                ids.append(evidence_id)
            entry = {**entry, "supporting_evidence": ids}
        ledger.append(entry)
    return {"claims": claims, "claim_ledger": ledger}


def retrieve_claims_by_section(state: dict[str, Any], section_id: str) -> list[dict]:
    return [c for c in state.get("claim_ledger", []) if c.get("section_id") == section_id]


def retrieve_contradictory_evidence(state: dict[str, Any]) -> list[dict]:
    return list(state.get("contradiction_fragments", []))
