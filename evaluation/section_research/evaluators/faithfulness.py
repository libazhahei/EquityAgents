"""Build evidence packs for faithfulness / judge prompts."""

from __future__ import annotations

from typing import Any

from evaluation.section_research.types import EvidencePack


def _as_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def build_evidence_pack(
    final_state: dict[str, Any],
    *,
    tool_outputs: list[dict[str, Any]] | None = None,
) -> EvidencePack:
    section_out = final_state.get("section_research_output") or {}
    if not section_out and isinstance(final_state.get("section_research_outputs"), dict):
        sid = final_state.get("section_id")
        section_out = (final_state.get("section_research_outputs") or {}).get(sid) or {}

    citations = list(
        section_out.get("citations")
        or final_state.get("citations")
        or []
    )
    evidence_ledger = _as_list(final_state.get("evidence_ledger"))
    pending_evidence = _as_list(final_state.get("pending_evidence"))
    search_memory = _as_list(final_state.get("search_memory"))

    # Answer-card citations
    answer_cards = section_out.get("answer_cards") or final_state.get("answer_cards") or {}
    if isinstance(answer_cards, dict):
        for card in answer_cards.values():
            if isinstance(card, dict):
                citations.extend(_as_list(card.get("citations")))

    return EvidencePack(
        tool_outputs=list(tool_outputs or []),
        citations=citations,
        evidence_ledger=evidence_ledger,
        pending_evidence=pending_evidence,
        search_memory=search_memory,
    )


def summarize_evidence_for_prompt(evidence: EvidencePack, *, max_items: int = 12) -> str:
    parts: list[str] = []

    if evidence.evidence_ledger:
        parts.append("### evidence_ledger")
        for item in evidence.evidence_ledger[:max_items]:
            if isinstance(item, dict):
                claim = item.get("claim") or item.get("text") or item.get("summary") or str(item)[:200]
                source = item.get("source") or item.get("citation") or ""
                parts.append(f"- {claim} | source={source}")
            else:
                parts.append(f"- {str(item)[:200]}")

    if evidence.citations:
        parts.append("### citations")
        for cit in evidence.citations[:max_items]:
            if isinstance(cit, dict):
                parts.append(
                    f"- {cit.get('title') or cit.get('url') or cit.get('source') or cit}"
                )
            else:
                parts.append(f"- {cit}")

    if evidence.tool_outputs:
        parts.append("### tool_outputs (names + truncated)")
        for toot in evidence.tool_outputs[:max_items]:
            name = toot.get("name") or "?"
            out = toot.get("outputs") or {}
            snippet = str(out)[:240].replace("\n", " ")
            parts.append(f"- {name}: {snippet}")

    if evidence.pending_evidence:
        parts.append(f"### pending_evidence count={len(evidence.pending_evidence)}")

    if not parts:
        return "(no evidence_ledger / citations / tool_outputs available)"
    return "\n".join(parts)
