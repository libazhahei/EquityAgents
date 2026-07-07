"""Memory pruning, merge, and confidence decay."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.memory.similarity import text_similarity


def _parse_created_at(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _referenced_evidence_ids(state: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for claim in state.get("claim_ledger", []):
        refs.update(claim.get("supporting_evidence", []))
        refs.update(claim.get("contradicting_evidence", []))
    for claim in state.get("claims", []):
        refs.update(claim.get("supporting_evidence_ids", []))
        refs.update(claim.get("contradicting_evidence_ids", []))
    for assumption in state.get("assumption_ledger", []):
        refs.update(assumption.get("evidence_ids", []))
    return refs


def merge_similar_evidence(state: dict[str, Any], threshold: float = 0.85) -> dict[str, Any]:
    ledger = list(state.get("evidence_ledger", []))
    if not ledger:
        return {}
    inactive = [e for e in ledger if e.get("status") in {"archived", "merged"}]
    active = [e for e in ledger if e.get("status", "active") not in {"archived", "merged"}]
    survivors: list[dict[str, Any]] = []
    merged_out: list[dict[str, Any]] = []
    for entry in active:
        quote = entry.get("quote", "")
        match_idx = None
        for idx, kept in enumerate(survivors):
            if text_similarity(quote, kept.get("quote", "")) >= threshold:
                match_idx = idx
                break
        if match_idx is None:
            survivors.append(entry)
            continue
        kept = survivors[match_idx]
        keep_new = (
            float(entry.get("reliability_score", 0.5)) > float(kept.get("reliability_score", 0.5))
            or (
                float(entry.get("reliability_score", 0.5)) == float(kept.get("reliability_score", 0.5))
                and len(quote) > len(kept.get("quote", ""))
            )
        )
        if keep_new:
            merged_out.append({**kept, "status": "merged", "merged_into": entry.get("evidence_id", "")})
            survivors[match_idx] = entry
        else:
            merged_out.append({**entry, "status": "merged", "merged_into": kept.get("evidence_id", "")})
    if not merged_out:
        return {}
    return {"evidence_ledger": survivors + merged_out + inactive}


def prune_stale_evidence(state: dict[str, Any], max_age_days: int = 30) -> dict[str, Any]:
    refs = _referenced_evidence_ids(state)
    now = datetime.utcnow()
    ledger = []
    changed = False
    for entry in state.get("evidence_ledger", []):
        if entry.get("status") in {"archived", "merged"}:
            ledger.append(entry)
            continue
        eid = entry.get("evidence_id", "")
        created = _parse_created_at(entry.get("created_at", "")) or _parse_created_at(entry.get("date", ""))
        age_days = (now - created).days if created else 0
        if eid not in refs and age_days > max_age_days:
            ledger.append({**entry, "status": "archived"})
            changed = True
        else:
            ledger.append(entry)
    return {"evidence_ledger": ledger} if changed else {}


def decay_claim_confidence(
    state: dict[str, Any],
    *,
    decay_rate: float = 0.95,
    floor: float = 0.1,
) -> dict[str, Any]:
    now = datetime.utcnow()
    claims = list(state.get("claims", []))
    claim_ledger = list(state.get("claim_ledger", []))
    changed = False

    def _decay_entry(entry: dict[str, Any], confidence_key: str = "confidence") -> dict[str, Any]:
        nonlocal changed
        if entry.get("is_core_thesis"):
            return entry
        created = _parse_created_at(entry.get("created_at", ""))
        if not created:
            return entry
        days = max(0, (now - created).days)
        if days <= 0:
            return entry
        factor = decay_rate ** days
        old = float(entry.get(confidence_key, 0.5))
        new = max(floor, old * factor)
        if abs(new - old) < 1e-6:
            return entry
        changed = True
        return {**entry, confidence_key: new}

    claims = [_decay_entry(c) for c in claims]
    claim_ledger = [_decay_entry(c) for c in claim_ledger]
    return {"claims": claims, "claim_ledger": claim_ledger} if changed else {}


def run_memory_maintenance(state: dict[str, Any], deps: Any = None) -> dict[str, Any]:
    er = {}
    if deps is not None:
        er = getattr(deps, "config", {}).get("equity_research", {})
    updates: dict[str, Any] = {}
    updates.update(merge_similar_evidence(
        {**state, **updates},
        threshold=float(er.get("memory_merge_threshold", 0.85)),
    ))
    updates.update(prune_stale_evidence(
        {**state, **updates},
        max_age_days=int(er.get("memory_prune_max_age_days", 30)),
    ))
    updates.update(decay_claim_confidence(
        {**state, **updates},
        decay_rate=float(er.get("memory_claim_decay_rate", 0.95)),
    ))
    return updates
