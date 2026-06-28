"""Quality verification tools."""

from __future__ import annotations

from typing import Any

import httpx


def citation_checker(urls: list[str]) -> dict[str, Any]:
    report = []
    for url in urls:
        status = "unknown"
        try:
            with httpx.Client(timeout=10.0, follow_redirects=True) as client:
                resp = client.head(url)
                status = "ok" if resp.status_code < 400 else f"http_{resp.status_code}"
        except Exception as exc:
            status = f"error:{exc}"
        report.append({"url": url, "status": status})
    return {"report": report}


def claim_evidence_checker(claims: list[dict], evidence: list[dict]) -> dict[str, Any]:
    evidence_ids = {e.get("evidence_id") or e.get("fragment_id") for e in evidence}
    rows = []
    for claim in claims:
        supporting = claim.get("supporting_evidence_ids", [])
        has_support = any(eid in evidence_ids for eid in supporting)
        rows.append({
            "claim_id": claim.get("claim_id"),
            "supported": has_support,
            "supporting_count": len(supporting),
        })
    return {"claims": rows, "unsupported": [r for r in rows if not r["supported"]]}


def coverage_evaluator(artifact: dict[str, Any], criteria: list[str]) -> dict[str, Any]:
    text = str(artifact).lower()
    covered = [c for c in criteria if c.lower() in text]
    return {
        "criteria": criteria,
        "covered": covered,
        "missing": [c for c in criteria if c not in covered],
        "coverage_pct": len(covered) / len(criteria) if criteria else 1.0,
    }


def conflict_detector(evidence: list[dict] | dict) -> dict[str, Any]:
    items = evidence if isinstance(evidence, list) else evidence.get("items", [])
    conflicts = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a.get("polarity") and b.get("polarity") and a["polarity"] != b["polarity"]:
                if a.get("metric") == b.get("metric"):
                    conflicts.append({"a": a.get("evidence_id"), "b": b.get("evidence_id"), "metric": a.get("metric")})
    return {"conflicts": conflicts, "count": len(conflicts)}
