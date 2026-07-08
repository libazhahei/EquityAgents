"""Late-stage section writing agents."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.consensus_schemas import get_consensus_view_for_prompt
from tradingagents.equity_research.state.schemas import ClaimStatus, SectionDraft
from tradingagents.equity_research.templates.report_template import (
    MVP1_DISPLAY_ORDER,
    MVP1_REPORT_TEMPLATE,
)
from tradingagents.equity_research.tools.evidence_memory import retrieve_claims_by_section


def _light_polish_section_text(
    deps: EquityResearchDeps,
    *,
    ticker: str,
    section_title: str,
    section_id: str,
    base_text: str,
    required_outputs: list[str],
) -> str:
    """Apply light editorial cleanup while preserving meaning and citations."""
    if not base_text.strip():
        return ""
    prompt = (
        f"Lightly edit the following equity research section for {ticker}.\n"
        f"Section: {section_title} ({section_id})\n"
        f"Required outputs: {required_outputs}\n\n"
        "Rules:\n"
        "- Preserve all factual claims and numbers unless correcting obvious grammar only.\n"
        "- Preserve citation markers and URLs verbatim.\n"
        "- Do not introduce new unsupported claims.\n"
        "- Keep original structure and intent, only improve readability/formatting.\n"
        "- Return markdown only.\n\n"
        f"Original section draft:\n{base_text}"
    )
    try:
        response = deps.quick_llm.invoke(prompt)
        polished = response.content if hasattr(response, "content") else str(response)
        polished = str(polished).strip()
        return polished or base_text
    except Exception:
        return base_text


def _build_section_question_coverage(
    state: dict[str, Any],
    section_id: str,
    section_output: dict[str, Any],
) -> dict[str, Any]:
    section_plan = (state.get("section_plans") or {}).get(section_id, {}) or {}
    nodes = list(section_plan.get("nodes") or [])
    answer_cards = dict(section_output.get("answer_cards") or {})
    unresolved_gaps = list(section_output.get("unresolved_gaps") or [])

    rows: list[dict[str, Any]] = []
    for node in nodes:
        question_id = str(node.get("id", "")).strip()
        if not question_id:
            continue
        card = answer_cards.get(question_id) or {}
        confidence = float(card.get("confidence") or 0.0)
        verified_facts = list(card.get("verified_facts") or [])
        open_gaps = list(card.get("open_gaps") or [])
        if not card:
            status = "missing"
        elif confidence >= 0.7 and verified_facts and not open_gaps:
            status = "answered"
        else:
            status = "partial"
        rows.append({
            "question_id": question_id,
            "question": str(node.get("question", "")),
            "level": int(node.get("level", 0)),
            "status": status,
            "confidence": confidence,
            "evidence_count": len(verified_facts),
            "open_gaps_count": len(open_gaps),
        })

    answered = sum(1 for r in rows if r["status"] == "answered")
    partial = sum(1 for r in rows if r["status"] == "partial")
    missing = sum(1 for r in rows if r["status"] == "missing")
    root = next((r for r in rows if r.get("level", 0) == 0), rows[0] if rows else None)
    return {
        "section_id": section_id,
        "root_question_id": root.get("question_id") if root else None,
        "root_question": root.get("question") if root else "",
        "total_questions": len(rows),
        "answered_questions": answered,
        "partial_questions": partial,
        "missing_questions": missing,
        "rows": rows,
        "unresolved_gaps": unresolved_gaps,
    }


def create_write_investment_summary(deps: EquityResearchDeps):
    def write_investment_summary(state: dict[str, Any]) -> dict[str, Any]:
        section_id = "1_investment_summary"
        template = MVP1_REPORT_TEMPLATE[section_id]
        section_outputs = state.get("section_research_outputs", {})
        section_output = dict(section_outputs.get(section_id) or {})
        verified = [c for c in state.get("claims", []) if c.get("status") == ClaimStatus.VERIFIED.value]
        gaps = state.get("expectation_gaps", [])
        consensus = get_consensus_view_for_prompt(state)
        scenario = state.get("scenario_analysis", {})
        base_text = str(section_output.get("final_section_text", "") or "").strip()
        if base_text:
            body = _light_polish_section_text(
                deps,
                ticker=state["ticker"],
                section_title=template["title"],
                section_id=section_id,
                base_text=base_text,
                required_outputs=template["required_outputs"],
            )
        else:
            prompt = (
                f"Write Investment Summary for {state['ticker']}.\n"
                f"Rating: {state.get('rating')}\n"
                f"Target price: {state.get('target_price')}\n"
                f"Current price: {state.get('current_price')}\n"
                f"Dividend yield: {state.get('dividend_yield_pct', 0)}\n"
                f"Consensus: {json.dumps(consensus, default=str)[:1500]}\n"
                f"Expectation gaps: {json.dumps(gaps[:4], default=str)}\n"
                f"Scenario analysis: {json.dumps(scenario, default=str)[:1000]}\n"
                f"Verified claims: {json.dumps(verified[:8], default=str)[:3000]}\n"
                f"Required: {template['required_outputs']}\n"
                "Include variant_view and catalyst_timeline. Ensure rating/target are consistent with upside."
            )
            response = deps.deep_llm.invoke(prompt)
            body = response.content if hasattr(response, "content") else str(response)
        draft = SectionDraft(
            section_id=section_id,
            title=template["title"],
            body_markdown=body,
            claim_ids=[c.get("claim_id", "") for c in verified],
            completed_outputs=_infer_completed_outputs(body, template["required_outputs"]),
        )
        drafts = dict(state.get("section_drafts", {}))
        drafts[section_id] = draft.model_dump()
        section_question_coverage = dict(state.get("section_question_coverage", {}))
        section_question_coverage[section_id] = _build_section_question_coverage(
            state,
            section_id,
            section_output,
        )
        coverage = dict(state.get("section_coverage", {}))
        if section_id in coverage:
            coverage[section_id]["completed_outputs"] = draft.completed_outputs
            coverage[section_id]["coverage_score"] = len(draft.completed_outputs) / max(
                len(template["required_outputs"]), 1
            )
        updates = {
            "section_drafts": drafts,
            "section_coverage": coverage,
            "section_question_coverage": section_question_coverage,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "write_investment_summary"))
        return updates

    return write_investment_summary


def create_write_remaining_sections(deps: EquityResearchDeps):
    def write_remaining_sections(state: dict[str, Any]) -> dict[str, Any]:
        drafts = dict(state.get("section_drafts", {}))
        coverage = dict(state.get("section_coverage", {}))
        section_outputs = dict(state.get("section_research_outputs", {}))
        section_question_coverage = dict(state.get("section_question_coverage", {}))
        completed_sections = list(state.get("completed_sections", []))
        forecast = state.get("forecast_model") or {}
        valuation = state.get("valuation_model") or {}
        historical = state.get("historical_financials") or {}

        for section_id in MVP1_DISPLAY_ORDER:
            if section_id == "1_investment_summary":
                continue
            template = MVP1_REPORT_TEMPLATE.get(section_id, {})
            section_output = dict(section_outputs.get(section_id) or {})
            section_claims = retrieve_claims_by_section(state, section_id)
            legacy_claims = [
                c for c in state.get("claims", [])
                if c.get("section_id") == section_id
                and c.get("status") in (ClaimStatus.VERIFIED.value, ClaimStatus.PARTIALLY_SUPPORTED.value)
            ]
            claims_for_write = section_claims or legacy_claims
            base_text = str(section_output.get("final_section_text", "") or "").strip()
            if base_text:
                body = _light_polish_section_text(
                    deps,
                    ticker=state["ticker"],
                    section_title=template.get("title", section_id),
                    section_id=section_id,
                    base_text=base_text,
                    required_outputs=template.get("required_outputs", []),
                )
            else:
                claims_text = json.dumps(claims_for_write[:10], default=str)
                prompt = (
                    f"Write the '{template.get('title', section_id)}' section for {state['ticker']}.\n"
                    f"Claims:\n{claims_text}\n"
                    f"Forecast: {json.dumps(forecast, default=str)[:1200]}\n"
                    f"Valuation: {json.dumps(valuation, default=str)[:800]}\n"
                    f"Historical: {json.dumps(historical, default=str)[:800]}\n"
                    f"Risk map: {json.dumps(state.get('risk_map', []), default=str)[:800]}\n"
                    f"Required outputs: {template.get('required_outputs', [])}\n"
                    "Use markdown. Cite evidence by [doc_id] where applicable. "
                    "Do not add unsupported new claims."
                )
                response = deps.deep_llm.invoke(prompt)
                body = response.content if hasattr(response, "content") else str(response)
            draft = SectionDraft(
                section_id=section_id,
                title=template.get("title", section_id),
                body_markdown=body,
                claim_ids=[c.get("claim_id", "") for c in claims_for_write],
                completed_outputs=_infer_completed_outputs(body, template.get("required_outputs", [])),
                review_passed=True,
            )
            drafts[section_id] = draft.model_dump()
            if section_id in coverage:
                coverage[section_id]["completed_outputs"] = draft.completed_outputs
                coverage[section_id]["coverage_score"] = len(draft.completed_outputs) / max(
                    len(template.get("required_outputs", [])), 1
                )
            if section_id not in completed_sections:
                completed_sections.append(section_id)
            section_question_coverage[section_id] = _build_section_question_coverage(
                state,
                section_id,
                section_output,
            )

        updates = {
            "section_drafts": drafts,
            "section_coverage": coverage,
            "section_question_coverage": section_question_coverage,
            "completed_sections": completed_sections,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "write_remaining_sections"))
        return updates

    return write_remaining_sections


# Backward-compatible aliases
create_write_investment_focus = create_write_investment_summary
create_write_section = create_write_remaining_sections


def create_review_section(deps: EquityResearchDeps):
    """Legacy no-op; section review happens in final_consistency_check."""
    def review_section(state: dict[str, Any]) -> dict[str, Any]:
        return deps.trace(state, "review_section", {"skipped": True})

    return review_section


def _infer_completed_outputs(body: str, required: list[str]) -> list[str]:
    body_lower = body.lower()
    completed = []
    for output in required:
        tokens = output.replace("_", " ").split()
        if any(t in body_lower for t in tokens if len(t) > 3):
            completed.append(output)
    return completed or required[: max(1, len(required) // 2)]
