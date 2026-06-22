
from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.computation.valuation_mock import check_rating_upside_consistency
from tradingagents.equity_research.evaluation.aggregators import aggregate_ic_scores
from tradingagents.equity_research.export.markdown_memory import export_research_memory
from tradingagents.equity_research.state.ledgers import IssueLedgerEntry, sync_ledgers_from_legacy
from tradingagents.equity_research.state.schemas import ClaimStatus, ClaimType, InvestmentCommitteeReview
from tradingagents.equity_research.templates.report_template import (
    MVP1_DISPLAY_ORDER,
    get_investment_summary_template,
)


def create_investment_committee_review(deps: EquityResearchDeps):
    def investment_committee_review(state: dict[str, Any]) -> dict[str, Any]:
        rating = state.get("rating")
        target_price = state.get("target_price")
        current_price = float(state.get("current_price") or 0)
        dividend_yield = float(state.get("dividend_yield_pct") or 0)
        upside = 0.0
        if current_price > 0 and target_price:
            upside = (float(target_price) - current_price) / current_price

        # Aggregated evaluation
        eval_result = aggregate_ic_scores(state)
        blocking = list(eval_result.blocking_issues)
        warnings = list(eval_result.warnings)

        if rating:
            blocking.extend(check_rating_upside_consistency(rating, upside, dividend_yield))

        unsupported_rec = [
            c for c in state.get("claims", [])
            if c.get("claim_type") == ClaimType.RECOMMENDATION.value
            and c.get("status") == ClaimStatus.UNSUPPORTED.value
        ]
        if unsupported_rec:
            blocking.append("unsupported_recommendation_claim")

        graph = state.get("research_graph", {})
        if not graph.get("best_node_id"):
            warnings.append("no_best_thesis_node")

        if rating and deps.perplexity and deps.perplexity.api_key:
            verify = deps.perplexity.finance_verify(
                state["ticker"],
                f"Rating {rating} with target price {target_price}",
            )
            if not verify.get("answer"):
                warnings.append("finance_search_verification_inconclusive")

        score = eval_result.aggregate_score
        review = InvestmentCommitteeReview(
            passed=len(blocking) == 0,
            score=max(0.0, score),
            blocking_issues=blocking,
            warnings=warnings,
            rating=rating,
            target_price=target_price,
        )

        issue_ledger = list(state.get("issue_ledger", []))
        for b in blocking:
            issue_ledger.append(IssueLedgerEntry(
                issue_id=f"ic_{b}",
                gate="investment_committee_review",
                message=b,
                severity="blocking",
            ).model_dump())

        updates = {
            "ic_review": review.model_dump(),
            "issue_ledger": issue_ledger,
            "review_findings": state.get("review_findings", []) + blocking,
            "last_updated": datetime.utcnow().isoformat(),
        }
        if blocking:
            updates.setdefault("errors", []).extend(blocking)
        updates.update(sync_ledgers_from_legacy({**state, **updates}))
        updates.update(deps.trace({**state, **updates}, "investment_committee_review"))
        return updates

    return investment_committee_review


def create_assemble_report(deps: EquityResearchDeps):
    def assemble_report(state: dict[str, Any]) -> dict[str, Any]:
        drafts = state.get("section_drafts", {})
        template_summary = get_investment_summary_template()
        parts = [
            f"# Equity Research Report: {state.get('company_name', state['ticker'])} ({state['ticker']})",
            f"**Rating**: {state.get('rating', 'N/A')} | **Target**: {state.get('target_price', 'N/A')} "
            f"| **Current**: {state.get('current_price', 'N/A')}",
            f"**Report ID**: {state.get('report_id')} | **Generated**: {datetime.utcnow().isoformat()}",
            f"**Rating basis**: {template_summary.get('rating_basis', '12_month_total_return')}",
            "",
        ]
        for sid in MVP1_DISPLAY_ORDER:
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
                    f"- **{ch.get('title')}**: {ch.get('time_range', 'N/A')} | "
                    f"source={ch.get('data_source', 'N/A')}"
                )

        if state.get("compliance_flags"):
            parts.append("## Compliance")
            for flag in state["compliance_flags"]:
                parts.append(f"- {flag.get('message', flag)}")

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
