"""Rule-based evidence conflict detection."""

from __future__ import annotations

import re
import uuid
from typing import Any


def _normalize_metric(metric: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", metric.lower()).strip("_")


def _parse_numeric_direction(value: str, direction: str = "") -> tuple[float | None, str]:
    text = f"{value} {direction}".strip().lower()
    if not text:
        return None, ""
    if any(tok in text for tok in ("decline", "decrease", "down", "fall", "negative", "contract")):
        return None, "down"
    if any(tok in text for tok in ("growth", "increase", "up", "rise", "positive", "expand")):
        return None, "up"
    match = re.search(r"(-?\d+(?:\.\d+)?)\s*%?", text)
    if not match:
        return None, ""
    num = float(match.group(1))
    if num < 0:
        return num, "down"
    if num > 0:
        return num, "up"
    return num, "flat"


def _values_conflict(a_value: str, a_dir: str, b_value: str, b_dir: str) -> bool:
    a_num, a_direction = _parse_numeric_direction(a_value, a_dir)
    b_num, b_direction = _parse_numeric_direction(b_value, b_dir)
    if a_direction and b_direction and a_direction != b_direction and "flat" not in (a_direction, b_direction):
        return True
    if a_num is not None and b_num is not None:
        if (a_num > 0) != (b_num > 0):
            return True
        if a_num != 0 and b_num != 0 and (a_num > 0) == (b_num > 0):
            ratio = max(abs(a_num), abs(b_num)) / max(min(abs(a_num), abs(b_num)), 0.01)
            return ratio >= 2.0
    return False


def detect_conflicts(
    new_entry: dict[str, Any],
    existing_ledger: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return conflict records between new evidence and existing ledger entries."""
    metric = _normalize_metric(new_entry.get("metric", ""))
    if not metric:
        return []
    conflicts: list[dict[str, Any]] = []
    for existing in existing_ledger:
        if existing.get("evidence_id") == new_entry.get("evidence_id"):
            continue
        if existing.get("status") in {"archived", "merged"}:
            continue
        if _normalize_metric(existing.get("metric", "")) != metric:
            continue
        if not _values_conflict(
            str(new_entry.get("value", "")),
            str(new_entry.get("direction", "")),
            str(existing.get("value", "")),
            str(existing.get("direction", "")),
        ):
            continue
        preferred = (
            "new"
            if float(new_entry.get("reliability_score", 0.5)) >= float(existing.get("reliability_score", 0.5))
            else "existing"
        )
        if float(new_entry.get("reliability_score", 0.5)) >= 0.8:
            preferred = "new"
        elif float(existing.get("reliability_score", 0.5)) >= 0.8:
            preferred = "existing"
        conflicts.append({
            "conflict_id": f"cnf_{uuid.uuid4().hex[:8]}",
            "metric": metric,
            "evidence_a": new_entry.get("evidence_id", ""),
            "evidence_b": existing.get("evidence_id", ""),
            "preferred": preferred,
            "reason": "metric_value_or_direction_conflict",
        })
    return conflicts


def apply_conflicts_to_state(
    state: dict[str, Any],
    new_entry: dict[str, Any],
    conflicts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Mutate ledgers/claims based on detected conflicts."""
    if not conflicts:
        return {}
    ledger = list(state.get("evidence_ledger", []))
    contradiction_fragments = list(state.get("contradiction_fragments", []))
    memory_conflicts = list(state.get("memory_conflicts", []))
    claims = list(state.get("claims", []))
    claim_ledger = list(state.get("claim_ledger", []))

    new_id = new_entry.get("evidence_id", "")
    new_contra = set(new_entry.get("contradicting_evidence", []))

    for conflict in conflicts:
        other_id = conflict["evidence_b"]
        new_contra.add(other_id)
        memory_conflicts.append(conflict)
        for idx, entry in enumerate(ledger):
            if entry.get("evidence_id") == other_id:
                other_contra = set(entry.get("contradicting_evidence", []))
                other_contra.add(new_id)
                resolution = "preferred" if conflict.get("preferred") == "existing" else ""
                ledger[idx] = {
                    **entry,
                    "contradicting_evidence": sorted(other_contra),
                    "conflict_resolution": resolution,
                }
                contradiction_fragments.append({
                    "fragment_id": other_id,
                    "metric": conflict.get("metric", ""),
                    "conflict_id": conflict.get("conflict_id", ""),
                })
        contradiction_fragments.append({
            "fragment_id": new_id,
            "metric": conflict.get("metric", ""),
            "conflict_id": conflict.get("conflict_id", ""),
        })

    updated_new = {
        **new_entry,
        "contradicting_evidence": sorted(new_contra),
        "conflict_resolution": "preferred" if any(c.get("preferred") == "new" for c in conflicts) else "",
    }
    for idx, entry in enumerate(ledger):
        if entry.get("evidence_id") == new_id:
            ledger[idx] = updated_new
            break

    conflict_ids = {c["evidence_a"] for c in conflicts} | {c["evidence_b"] for c in conflicts}
    for idx, claim in enumerate(claims):
        supporting = set(claim.get("supporting_evidence_ids", []))
        if supporting & conflict_ids:
            claims[idx] = {
                **claim,
                "confidence": max(0.0, float(claim.get("confidence", 0.5)) * 0.8),
            }
    for idx, entry in enumerate(claim_ledger):
        supporting = set(entry.get("supporting_evidence", []))
        if supporting & conflict_ids:
            claim_ledger[idx] = {
                **entry,
                "confidence": max(0.0, float(entry.get("confidence", 0.5)) * 0.8),
            }

    return {
        "evidence_ledger": ledger,
        "contradiction_fragments": contradiction_fragments,
        "memory_conflicts": memory_conflicts,
        "claims": claims,
        "claim_ledger": claim_ledger,
    }
