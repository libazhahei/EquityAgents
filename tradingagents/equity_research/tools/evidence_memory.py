"""Evidence and memory tools for equity research ledgers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.memory.conflict import apply_conflicts_to_state, detect_conflicts
from tradingagents.equity_research.memory.similarity import text_similarity
from tradingagents.equity_research.state.ledgers import (
    assumption_dict_to_ledger_entry,
    claim_dict_to_ledger_entry,
    fragment_to_evidence_entry,
    write_to_ledger,
)


def _doc_reliability(deps: Any | None, doc_id: str) -> float | None:
    if not deps or not doc_id or not hasattr(deps, "documents"):
        return None
    doc = deps.documents.get_by_id(doc_id)
    if not doc:
        return None
    return float(doc.get("reliability_score", 0.5))


def store_evidence(
    state: dict[str, Any],
    fragment: dict[str, Any],
    *,
    deps: Any = None,
    created_by: str = "",
) -> dict[str, Any]:
    doc_id = fragment.get("doc_id", "")
    if deps is not None and doc_id and hasattr(deps.documents, "update_reliability"):
        deps.documents.update_reliability(doc_id, 0.02, reason="store_evidence")
    if "reliability_score" not in fragment:
        doc_rel = _doc_reliability(deps, doc_id)
        if doc_rel is not None:
            fragment = {**fragment, "reliability_score": doc_rel}
    if created_by:
        fragment = {**fragment, "created_by": created_by}
    entry = fragment_to_evidence_entry(fragment)
    if not entry.get("evidence_id"):
        entry["evidence_id"] = f"evid_{uuid.uuid4().hex[:8]}"
    entry["fragment_id"] = entry.get("fragment_id") or entry["evidence_id"]

    conflicts = detect_conflicts(entry, state.get("evidence_ledger", []))

    fragments = list(state.get("evidence_fragments", []))
    fragments.append({**fragment, "fragment_id": entry["evidence_id"]})

    updates: dict[str, Any] = {
        "evidence_fragments": fragments,
        "evidence_id": entry["evidence_id"],
    }
    updates.update(write_to_ledger(
        state,
        "evidence",
        entry,
        created_by=created_by,
        deps=deps,
    ))
    merged_state = {**state, **updates}
    conflict_updates = apply_conflicts_to_state(merged_state, entry, conflicts)
    if conflict_updates:
        updates.update(conflict_updates)
        if deps is not None and entry.get("evidence_id"):
            for ledger_entry in conflict_updates.get("evidence_ledger", []):
                if ledger_entry.get("evidence_id") == entry["evidence_id"]:
                    write_to_ledger(
                        {**merged_state, **updates},
                        "evidence",
                        ledger_entry,
                        created_by=created_by,
                        deps=deps,
                    )
                    break

    if deps is not None and hasattr(deps, "evidence"):
        ticker = state.get("ticker", "")
        quote = entry.get("quote", "")
        embedding = None
        if hasattr(deps, "embeddings"):
            embedding = deps.embeddings.embed(quote)
        deps.evidence.insert(
            ticker=ticker,
            doc_id=doc_id,
            excerpt_text=quote,
            fragment_id=entry["evidence_id"],
            embedding=embedding,
            fragment_type=fragment.get("fragment_type", "ledger"),
            source_reliability=str(fragment.get("source_reliability", "medium")),
        )
    return updates


def store_claim(
    state: dict[str, Any],
    claim: dict[str, Any],
    *,
    deps: Any = None,
    created_by: str = "",
) -> dict[str, Any]:
    if not claim.get("claim_id"):
        claim["claim_id"] = f"clm_{uuid.uuid4().hex[:8]}"
    if created_by:
        claim = {**claim, "created_by": created_by}
    ledger_entry = claim_dict_to_ledger_entry(claim)
    claims = list(state.get("claims", []))
    claims.append(claim)

    updates: dict[str, Any] = {
        "claims": claims,
        "claim_id": claim["claim_id"],
    }
    updates.update(write_to_ledger(
        state,
        "claim",
        ledger_entry,
        created_by=created_by,
        deps=deps,
    ))

    explicit_ids = list(claim.get("supporting_evidence_ids", []))
    if explicit_ids:
        for evidence_id in explicit_ids:
            updates.update(link_evidence_to_claim({**state, **updates}, claim["claim_id"], evidence_id, deps=deps))
    else:
        claim_text = claim.get("text", claim.get("claim", ""))
        for entry in state.get("evidence_ledger", []):
            if entry.get("status") in {"archived", "merged"}:
                continue
            if text_similarity(claim_text, entry.get("quote", "")) >= 0.7:
                updates.update(link_evidence_to_claim(
                    {**state, **updates},
                    claim["claim_id"],
                    entry.get("evidence_id", ""),
                    deps=deps,
                ))

    return updates


def store_assumption(
    state: dict[str, Any],
    assumption: dict[str, Any],
    *,
    deps: Any = None,
    created_by: str = "",
) -> dict[str, Any]:
    entry = assumption_dict_to_ledger_entry(assumption)
    if not entry.get("assumption_id"):
        entry["assumption_id"] = f"asm_{uuid.uuid4().hex[:8]}"
    if created_by:
        entry["created_by"] = created_by
    assumptions = list(state.get("model_assumptions", []))
    assumptions.append(entry)
    updates = {
        "model_assumptions": assumptions,
        "assumption_id": entry["assumption_id"],
    }
    updates.update(write_to_ledger(
        state,
        "assumption",
        entry,
        created_by=created_by,
        deps=deps,
    ))
    return updates


def link_evidence_to_claim(
    state: dict[str, Any],
    claim_id: str,
    evidence_id: str,
    *,
    deps: Any = None,
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

    updates: dict[str, Any] = {"claims": claims, "claim_ledger": ledger}
    if deps is not None:
        doc_id = ""
        for ev in state.get("evidence_ledger", []):
            if ev.get("evidence_id") == evidence_id:
                doc_id = ev.get("doc_id", "")
                break
        if doc_id and hasattr(deps.documents, "update_reliability"):
            deps.documents.update_reliability(doc_id, 0.05, reason="claim_citation")
    return updates


def retrieve_claims_by_section(state: dict[str, Any], section_id: str) -> list[dict]:
    return [c for c in state.get("claim_ledger", []) if c.get("section_id") == section_id]


def retrieve_contradictory_evidence(state: dict[str, Any]) -> list[dict]:
    return list(state.get("contradiction_fragments", []))
