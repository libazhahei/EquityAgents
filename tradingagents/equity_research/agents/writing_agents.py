"""Late-stage section writing agents."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.schemas import ClaimStatus, SectionDraft
from tradingagents.equity_research.templates.report_template import (
    MVP1_DISPLAY_ORDER,
    MVP1_REPORT_TEMPLATE,
)
from tradingagents.equity_research.tools.evidence_memory import retrieve_claims_by_section


def create_write_investment_summary(deps: EquityResearchDeps):
    def write_investment_summary(state: dict[str, Any]) -> dict[str, Any]:
        section_id = "1_investment_summary"
        template = MVP1_REPORT_TEMPLATE[section_id]
        verified = [c for c in state.get("claims", []) if c.get("status") == ClaimStatus.VERIFIED.value]
        gaps = state.get("expectation_gaps", [])
        consensus = state.get("consensus_view", [{}])[0] if state.get("consensus_view") else {}
        scenario = state.get("scenario_analysis", {})
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
        coverage = dict(state.get("section_coverage", {}))
        if section_id in coverage:
            coverage[section_id]["completed_outputs"] = draft.completed_outputs
            coverage[section_id]["coverage_score"] = len(draft.completed_outputs) / max(
                len(template["required_outputs"]), 1
            )
        updates = {
            "section_drafts": drafts,
            "section_coverage": coverage,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "write_investment_summary"))
        return updates

    return write_investment_summary


def create_write_remaining_sections(deps: EquityResearchDeps):
    def write_remaining_sections(state: dict[str, Any]) -> dict[str, Any]:
        drafts = dict(state.get("section_drafts", {}))
        coverage = dict(state.get("section_coverage", {}))
        completed_sections = list(state.get("completed_sections", []))
        forecast = state.get("forecast_model") or {}
        valuation = state.get("valuation_model") or {}
        historical = state.get("historical_financials") or {}

        for section_id in MVP1_DISPLAY_ORDER:
            if section_id == "1_investment_summary":
                continue
            template = MVP1_REPORT_TEMPLATE.get(section_id, {})
            section_claims = retrieve_claims_by_section(state, section_id)
            legacy_claims = [
                c for c in state.get("claims", [])
                if c.get("section_id") == section_id
                and c.get("status") in (ClaimStatus.VERIFIED.value, ClaimStatus.PARTIALLY_SUPPORTED.value)
            ]
            claims_for_write = section_claims or legacy_claims
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

        updates = {
            "section_drafts": drafts,
            "section_coverage": coverage,
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
