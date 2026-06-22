"""Section writing and review agents."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.schemas import ClaimStatus, SectionDraft
from tradingagents.equity_research.templates.report_template import MVP1_REPORT_TEMPLATE


def create_write_section(deps: EquityResearchDeps):
    def write_section(state: dict[str, Any]) -> dict[str, Any]:
        section_id = state.get("active_section_id", "")
        template = MVP1_REPORT_TEMPLATE.get(section_id, {})
        verified = [
            c for c in state.get("claims", [])
            if c.get("section_id") == section_id and c.get("status") == ClaimStatus.VERIFIED.value
        ]
        partial = [
            c for c in state.get("claims", [])
            if c.get("section_id") == section_id and c.get("status") == ClaimStatus.PARTIALLY_SUPPORTED.value
        ]
        claims_for_write = verified or partial
        if not claims_for_write and section_id not in ("5_earnings_forecast", "6_valuation"):
            state.setdefault("warnings", []).append(
                f"No verified claims for section {section_id}; draft may be thin."
            )

        claims_text = json.dumps(claims_for_write[:10], default=str)
        forecast = state.get("forecast_model") or {}
        valuation = state.get("valuation_model") or {}
        prompt = (
            f"Write the '{template.get('title', section_id)}' section for {state['ticker']}.\n"
            f"Verified claims:\n{claims_text}\n"
            f"Forecast model: {json.dumps(forecast, default=str)[:1500]}\n"
            f"Valuation: {json.dumps(valuation, default=str)[:1000]}\n"
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
        )
        drafts = dict(state.get("section_drafts", {}))
        drafts[section_id] = draft.model_dump()
        updates = {
            "section_drafts": drafts,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "write_section", {"section_id": section_id}))
        return updates

    return write_section


def create_write_investment_focus(deps: EquityResearchDeps):
    def write_investment_focus(state: dict[str, Any]) -> dict[str, Any]:
        section_id = "1_investment_focus"
        template = MVP1_REPORT_TEMPLATE[section_id]
        verified = [c for c in state.get("claims", []) if c.get("status") == ClaimStatus.VERIFIED.value]
        prompt = (
            f"Write Investment Focus for {state['ticker']}.\n"
            f"Rating: {state.get('rating')}\n"
            f"Target price: {state.get('target_price')}\n"
            f"Current price: {state.get('current_price')}\n"
            f"Verified claims summary: {json.dumps(verified[:8], default=str)[:3000]}\n"
            f"Required: {template['required_outputs']}\n"
            "Ensure rating and target price are consistent with upside."
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
        updates = {"section_drafts": drafts, "last_updated": datetime.utcnow().isoformat()}
        updates.update(deps.trace({**state, **updates}, "write_investment_focus"))
        return updates

    return write_investment_focus


def create_review_section(deps: EquityResearchDeps):
    def review_section(state: dict[str, Any]) -> dict[str, Any]:
        section_id = state.get("active_section_id", "")
        draft = state.get("section_drafts", {}).get(section_id, {})
        template = MVP1_REPORT_TEMPLATE.get(section_id, {})
        required = template.get("required_outputs", [])
        completed = draft.get("completed_outputs", [])
        missing = [o for o in required if o not in completed]
        min_evidence = template.get("required_evidence_min", 0)
        section_claims = [
            c for c in state.get("claims", [])
            if c.get("section_id") == section_id and c.get("status") == ClaimStatus.VERIFIED.value
        ]
        feedback = []
        passed = True
        if missing:
            feedback.append(f"Missing outputs: {missing}")
            passed = len(missing) <= len(required) // 2
        if len(section_claims) < min_evidence and section_id not in ("5_earnings_forecast", "6_valuation"):
            feedback.append(f"Insufficient verified claims: {len(section_claims)} < {min_evidence}")
            passed = False

        draft["review_passed"] = passed
        draft["review_feedback"] = "; ".join(feedback) if feedback else "OK"
        drafts = dict(state.get("section_drafts", {}))
        drafts[section_id] = draft

        completed_sections = list(state.get("completed_sections", []))
        coverage = dict(state.get("section_coverage", {}))
        if section_id not in completed_sections:
            completed_sections.append(section_id)
        if section_id in coverage:
            coverage[section_id]["completed_outputs"] = completed
            coverage[section_id]["coverage_score"] = len(completed) / max(len(required), 1)

        updates = {
            "section_drafts": drafts,
            "completed_sections": completed_sections,
            "section_coverage": coverage,
            "active_section_id": None,
            "last_updated": datetime.utcnow().isoformat(),
        }
        if not passed:
            updates.setdefault("warnings", []).extend(feedback)
        updates.update(deps.trace({**state, **updates}, "review_section", {"passed": passed}))
        return updates

    return review_section


def _infer_completed_outputs(body: str, required: list[str]) -> list[str]:
    body_lower = body.lower()
    completed = []
    for output in required:
        tokens = output.replace("_", " ").split()
        if any(t in body_lower for t in tokens if len(t) > 3):
            completed.append(output)
    return completed or required[: max(1, len(required) // 2)]
