"""Final review, report assembly, and markdown export."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.computation.valuation_mock import check_rating_upside_consistency
from tradingagents.equity_research.export.markdown_memory import export_research_memory
from tradingagents.equity_research.state.schemas import ClaimStatus, ClaimType, InvestmentCommitteeReview
from tradingagents.equity_research.templates.report_template import MVP1_SECTION_ORDER


def create_investment_committee_review(deps: EquityResearchDeps):
    def investment_committee_review(state: dict[str, Any]) -> dict[str, Any]:
        rating = state.get("rating")
        target_price = state.get("target_price")
        current_price = float(state.get("current_price") or 0)
        upside = 0.0
        if current_price > 0 and target_price:
            upside = (float(target_price) - current_price) / current_price

        blocking = []
        warnings = []
        if not rating:
            blocking.append("rating missing")
        if not target_price:
            blocking.append("target_price missing")
        if rating:
            blocking.extend(check_rating_upside_consistency(rating, upside))

        unsupported_rec = [
            c for c in state.get("claims", [])
            if c.get("claim_type") == ClaimType.RECOMMENDATION.value
            and c.get("status") == ClaimStatus.UNSUPPORTED.value
        ]
        if unsupported_rec:
            blocking.append("unsupported recommendation claim")

        verified_hypotheses = state.get("verified_hypothesis_ids", [])
        if not verified_hypotheses:
            warnings.append("No verified expectation-gap hypothesis")

        # Optional Perplexity finance verification on rating claim
        if rating and deps.perplexity.api_key:
            verify = deps.perplexity.finance_verify(
                state["ticker"],
                f"Rating {rating} with target price {target_price}",
            )
            if not verify.get("answer"):
                warnings.append("Finance search verification inconclusive")

        score = 1.0 - 0.2 * len(blocking) - 0.05 * len(warnings)
        review = InvestmentCommitteeReview(
            passed=len(blocking) == 0,
            score=max(0.0, score),
            blocking_issues=blocking,
            warnings=warnings,
            rating=rating,
            target_price=target_price,
        )
        updates = {
            "ic_review": review.model_dump(),
            "last_updated": datetime.utcnow().isoformat(),
        }
        if blocking:
            updates.setdefault("errors", []).extend(blocking)
        updates.update(deps.trace({**state, **updates}, "investment_committee_review"))
        return updates

    return investment_committee_review


def create_assemble_report(deps: EquityResearchDeps):
    def assemble_report(state: dict[str, Any]) -> dict[str, Any]:
        drafts = state.get("section_drafts", {})
        order = ["1_investment_focus"] + [s for s in MVP1_SECTION_ORDER if s != "1_investment_focus"]
        # Reorder: investment focus first in final doc
        display_order = ["1_investment_focus", "2_company_overview", "3_industry_and_competition",
                         "5_earnings_forecast", "6_valuation", "7_risks"]
        parts = [
            f"# Equity Research Report: {state.get('company_name', state['ticker'])} ({state['ticker']})",
            f"**Rating**: {state.get('rating', 'N/A')} | **Target**: {state.get('target_price', 'N/A')} "
            f"| **Current**: {state.get('current_price', 'N/A')}",
            f"**Report ID**: {state.get('report_id')} | **Generated**: {datetime.utcnow().isoformat()}",
            "",
        ]
        for sid in display_order:
            draft = drafts.get(sid, {})
            if draft:
                parts.append(f"## {draft.get('title', sid)}")
                parts.append(draft.get("body_markdown", ""))
                parts.append("")

        charts = state.get("chart_placeholders", [])
        if charts:
            parts.append("## Chart Placeholders")
            for ch in charts:
                parts.append(
                    f"- **{ch.get('title')}**: {ch.get('time_range')} | "
                    f"x={ch.get('x_axis')} y={ch.get('y_axis')} | "
                    f"source={ch.get('data_source')} | method={ch.get('processing_method')}"
                )

        final_report = "\n".join(parts)
        updates = {
            "final_report": final_report,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "assemble_report"))
        return updates

    return assemble_report


def create_markdown_memory_export(deps: EquityResearchDeps):
    def markdown_memory_export(state: dict[str, Any]) -> dict[str, Any]:
        path = export_research_memory(state, deps.config)
        updates = {
            "last_updated": datetime.utcnow().isoformat(),
            "_export_path": path,
        }
        updates.update(deps.trace({**state, **updates}, "markdown_memory_export", {"path": path}))
        return updates

    return markdown_memory_export
