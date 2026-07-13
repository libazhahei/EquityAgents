"""Deterministic step payloads for verify / compare / calculate executor steps."""

from __future__ import annotations

import json
from typing import Any

_PAYLOAD_ACTIONS = frozenset({"verify", "compare", "calculate"})

_EVIDENCE_CAP = 8
_QUOTE_CAP = 240
_CLAIMS_CAP = 15
_URLS_CAP = 20
_CALC_STORE_CAP = 8

_METADATA_ALIASES: dict[str, tuple[str, ...]] = {
    "source_type": ("source_type", "source", "form"),
    "fiscal_quarter_or_date": ("fiscal_quarter_or_date", "period", "date"),
    "platform": ("platform", "vendor"),
    "traceable_ref": ("traceable_ref", "url", "doc_id", "filing_url"),
}


def build_step_payload(state: dict[str, Any], action: str) -> dict[str, Any]:
    """Assemble a structured payload for computation-group consumer steps."""
    action_l = (action or "").strip().lower()
    if action_l not in _PAYLOAD_ACTIONS:
        return {"status": "skipped", "action": action_l, "reason": "action_not_payloadable"}

    active_task = state.get("active_task") or {}
    qid = str(active_task.get("question_id") or "general")
    section_id = str(state.get("section_id") or "")

    evidence_all = _as_dict_list(state.get("evidence_ledger")) + _as_dict_list(
        state.get("evidence_fragments")
    )
    evidence_selected, evidence_fallback = _filter_evidence(evidence_all, qid)
    claims_all = _as_dict_list(state.get("claim_ledger") or state.get("claims"))
    claims_selected = _filter_claims(claims_all, evidence_selected, section_id)

    omitted: dict[str, int] = {}
    evidence_out, n_ev_omit = _cap_list(evidence_selected, _EVIDENCE_CAP)
    if n_ev_omit:
        omitted["evidence"] = n_ev_omit

    evidence_summaries = [_summarize_evidence(ev) for ev in evidence_out]
    metadata_gaps = [_metadata_gap_row(ev) for ev in evidence_out]

    if action_l == "calculate":
        numeric = [e for e in evidence_summaries if e.get("metric") or e.get("value")]
        calc_store = _as_dict_list(state.get("calculation_store"))
        calc_slice, n_calc_omit = _cap_list(calc_store, _CALC_STORE_CAP)
        if n_calc_omit:
            omitted["calculation_store"] = n_calc_omit
        payload: dict[str, Any] = {
            "action": action_l,
            "question_id": qid,
            "status": "ok" if (numeric or calc_slice) else "empty",
            "numeric_evidence": numeric,
            "calculation_store": [_slim_calc(c) for c in calc_slice],
            "filter": {"evidence_fallback": evidence_fallback},
        }
        if omitted:
            payload["truncated"] = True
            payload["omitted_counts"] = omitted
        if payload["status"] == "empty":
            payload["gaps"] = _empty_gaps(
                has_evidence=bool(evidence_summaries),
                has_claims=False,
                has_urls=False,
                reason="no_numeric_inputs",
            )
        return payload

    claims_out, n_cl_omit = _cap_list(claims_selected, _CLAIMS_CAP)
    if n_cl_omit:
        omitted["claims"] = n_cl_omit
    claim_summaries = [_summarize_claim(c) for c in claims_out]

    urls = _collect_urls(evidence_out, state.get("answer_cards") or {}, qid)
    urls_out, n_url_omit = _cap_list(urls, _URLS_CAP)
    if n_url_omit:
        omitted["urls"] = n_url_omit

    answer_card = _answer_card_slice(state.get("answer_cards") or {}, qid)

    has_content = bool(evidence_summaries or claim_summaries or urls_out or answer_card)
    payload = {
        "action": action_l,
        "question_id": qid,
        "status": "ok" if has_content else "empty",
        "evidence": evidence_summaries,
        "metadata_gaps": metadata_gaps,
        "claims": claim_summaries,
        "citation_urls": urls_out,
        "answer_card": answer_card,
        "filter": {"evidence_fallback": evidence_fallback},
    }
    if omitted:
        payload["truncated"] = True
        payload["omitted_counts"] = omitted
    if not has_content:
        payload["gaps"] = _empty_gaps(
            has_evidence=False,
            has_claims=False,
            has_urls=False,
            reason="no_evidence_claims_or_urls",
        )
    return payload


def format_step_payload_for_prompt(payload: dict[str, Any]) -> str:
    """Render payload as a compact JSON block for the HumanMessage."""
    body = json.dumps(payload, default=str, ensure_ascii=False, separators=(",", ":"))
    return f"\nStep payload (use as tool inputs; do not invent missing fields):\n{body}\n"


def _as_dict_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _filter_evidence(
    items: list[dict[str, Any]],
    qid: str,
) -> tuple[list[dict[str, Any]], bool]:
    matched = [e for e in items if str(e.get("question_id") or "") == qid]
    if matched:
        return matched, False
    # Fallback: untagged / empty qid only (never other qids)
    fallback = [e for e in items if not str(e.get("question_id") or "").strip()]
    return fallback, bool(fallback)


def _filter_claims(
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    section_id: str,
) -> list[dict[str, Any]]:
    ev_ids = {
        str(e.get("evidence_id") or e.get("fragment_id") or "")
        for e in evidence
        if e.get("evidence_id") or e.get("fragment_id")
    }
    ev_ids.discard("")

    linked: list[dict[str, Any]] = []
    for claim in claims:
        supporting = (
            claim.get("supporting_evidence_ids")
            or claim.get("supporting_evidence")
            or []
        )
        if not isinstance(supporting, list):
            supporting = []
        if ev_ids and any(str(sid) in ev_ids for sid in supporting):
            linked.append(claim)

    if linked:
        return linked

    if section_id:
        section_claims = [
            c for c in claims if str(c.get("section_id") or "") == section_id
        ]
        if section_claims:
            return section_claims

    return list(claims)


def _cap_list(items: list[Any], limit: int) -> tuple[list[Any], int]:
    if len(items) <= limit:
        return items, 0
    return items[:limit], len(items) - limit


def _truncate(text: str, limit: int = _QUOTE_CAP) -> str:
    text = str(text or "")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _summarize_evidence(ev: dict[str, Any]) -> dict[str, Any]:
    quote = (
        ev.get("quote")
        or ev.get("snippet")
        or ev.get("content")
        or ev.get("text")
        or ""
    )
    return {
        "evidence_id": ev.get("evidence_id") or ev.get("fragment_id") or "",
        "metric": ev.get("metric") or "",
        "value": ev.get("value") or "",
        "unit": ev.get("unit") or "",
        "period": ev.get("period") or ev.get("date") or "",
        "quote": _truncate(str(quote)),
        "source_type": ev.get("source_type") or ev.get("source") or "",
        "date": ev.get("date") or ev.get("period") or "",
        "url": ev.get("url") or ev.get("filing_url") or "",
        "traceable_ref": ev.get("traceable_ref") or ev.get("url") or ev.get("doc_id") or "",
        "question_id": ev.get("question_id") or "",
    }


def _summarize_claim(claim: dict[str, Any]) -> dict[str, Any]:
    supporting = (
        claim.get("supporting_evidence_ids")
        or claim.get("supporting_evidence")
        or []
    )
    if not isinstance(supporting, list):
        supporting = []
    return {
        "claim_id": claim.get("claim_id") or "",
        "claim": _truncate(str(claim.get("claim") or claim.get("text") or ""), 320),
        "supporting_evidence_ids": [str(x) for x in supporting],
        "confidence": claim.get("confidence"),
        "status": claim.get("status") or "",
    }


def _slim_calc(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "expression": item.get("expression") or item.get("formula") or "",
        "result": item.get("result") or item.get("value"),
        "metric": item.get("metric") or "",
        "question_id": item.get("question_id") or "",
    }


def _resolve_metadata_field(
    record: dict[str, Any],
    canonical: str,
) -> tuple[str, str]:
    """Return (value, status) where status is present | derived | missing."""
    aliases = _METADATA_ALIASES[canonical]
    primary = aliases[0]
    raw = record.get(primary)
    if raw not in (None, ""):
        return str(raw), "present"
    for alias in aliases[1:]:
        alt = record.get(alias)
        if alt not in (None, ""):
            return str(alt), "derived"
    return "", "missing"


def _metadata_gap_row(ev: dict[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    missing: list[str] = []
    derived: list[str] = []
    for canonical in _METADATA_ALIASES:
        value, status = _resolve_metadata_field(ev, canonical)
        fields[canonical] = {"value": value, "status": status}
        if status == "missing":
            missing.append(canonical)
        elif status == "derived":
            derived.append(canonical)
    return {
        "evidence_id": ev.get("evidence_id") or ev.get("fragment_id") or "",
        "fields": fields,
        "missing": missing,
        "derived": derived,
    }


def _collect_urls(
    evidence: list[dict[str, Any]],
    answer_cards: dict[str, Any],
    qid: str,
) -> list[str]:
    urls: list[str] = []
    for ev in evidence:
        for key in ("url", "filing_url", "traceable_ref"):
            val = ev.get(key)
            if isinstance(val, str) and val.startswith(("http://", "https://")):
                urls.append(val)
    card = answer_cards.get(qid) if isinstance(answer_cards, dict) else None
    if isinstance(card, dict):
        for cit in card.get("citations") or []:
            if isinstance(cit, dict):
                u = cit.get("url") or cit.get("traceable_ref") or ""
                if isinstance(u, str) and u.startswith(("http://", "https://")):
                    urls.append(u)
        for sa in card.get("source_attributions") or []:
            if isinstance(sa, dict):
                u = sa.get("url") or sa.get("traceable_ref") or ""
                if isinstance(u, str) and u.startswith(("http://", "https://")):
                    urls.append(u)
    # Dedupe preserving order
    return list(dict.fromkeys(urls))


def _answer_card_slice(answer_cards: dict[str, Any], qid: str) -> dict[str, Any] | None:
    if not isinstance(answer_cards, dict):
        return None
    card = answer_cards.get(qid)
    if not isinstance(card, dict):
        return None
    return {
        "question_id": qid,
        "quantified_claims": card.get("quantified_claims") or [],
        "source_attributions": card.get("source_attributions") or [],
        "open_gaps": card.get("open_gaps") or [],
    }


def _empty_gaps(
    *,
    has_evidence: bool,
    has_claims: bool,
    has_urls: bool,
    reason: str,
) -> list[str]:
    gaps = [reason]
    if not has_evidence:
        gaps.append("no_evidence")
    if not has_claims:
        gaps.append("no_claims")
    if not has_urls:
        gaps.append("no_urls")
    return gaps
