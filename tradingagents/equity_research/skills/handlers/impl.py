"""Python skill handlers — execution logic decoupled from .skill.md manifests.

Active runtime skills: broker_consensus_mining, variant_view_discovery,
market_assumption_decomposition. Handlers below marked LEGACY are kept for
reference; their .skill.md files live under definitions/legacy/.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from tradingagents.equity_research.memory.retrieval import build_memory_context
from tradingagents.equity_research.skills.base import LoadedSkill, SkillInput, SkillOutput
from tradingagents.equity_research.state.research_graph import init_research_graph_from_gaps
from tradingagents.equity_research.state.schemas import Claim, ClaimStatus, ClaimType, claim_to_dict
from tradingagents.equity_research.evaluation.aggregators import aggregate_ic_scores


class BrokerConsensusHandler:
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        fetch_estimates = tools.get("analyst_estimates_fetch")
        consensus_data = fetch_estimates(ticker) if fetch_estimates else {}
        summary = json.dumps(consensus_data, default=str)[:2000]
        claim = claim_to_dict(
            Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id="consensus",
                section_id="1_investment_summary",
                claim_type=ClaimType.RECOMMENDATION,
                text=f"Broker consensus snapshot for {ticker}: {summary}",
                status=ClaimStatus.PARTIALLY_SUPPORTED,
                confidence=0.6,
            )
        )
        if "store_claim" in tools:
            tools["store_claim"](state, claim)
        return SkillOutput(
            summary=summary,
            claims=[claim],
            confidence=0.6,
            artifacts={"consensus_data": consensus_data},
        )


class VariantViewDiscoveryHandler:
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        gaps = state.get("expectation_gaps", [])
        claims = []
        for gap in gaps[:3]:
            claim = claim_to_dict(
                Claim(
                    claim_id=str(uuid.uuid4()),
                    hypothesis_id=gap.get("gap_id", "gap"),
                    section_id="1_investment_summary",
                    claim_type=ClaimType.RECOMMENDATION,
                    text=gap.get("description", ""),
                    status=ClaimStatus.PARTIALLY_SUPPORTED,
                    confidence=0.65,
                    is_core_thesis=True,
                )
            )
            claims.append(claim)
            if "store_claim" in tools:
                tools["store_claim"](state, claim)
        summary = "; ".join(g.get("description", "") for g in gaps[:3])
        return SkillOutput(summary=summary, claims=claims, confidence=0.65)


class MarketAssumptionDecompositionHandler:
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        assumption_view = state.get("assumption_view") or state.get("structured_view") or {}
        assumption_map = assumption_view.get("assumption_map", [])
        priorities = assumption_view.get("top_research_priorities", [])
        summary = (
            f"Assumption decomposition for {ticker}: "
            f"{len(assumption_map)} assumptions, {len(priorities)} research priorities"
        )
        return SkillOutput(
            summary=summary[:2000],
            confidence=0.65,
            artifacts={
                "assumption_map": assumption_map,
                "top_research_priorities": priorities,
            },
        )


class BusinessModelAnalysisHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        fetch_financials = tools.get("financial_statement_fetch")
        financials = fetch_financials(ticker) if fetch_financials else {}
        drivers = state.get("business_drivers", [])
        text = f"Business drivers for {ticker}: {json.dumps(drivers, default=str)[:800]}"
        claim = claim_to_dict(
            Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id="business_model",
                section_id="3_business_model",
                claim_type=ClaimType.DRIVER,
                text=text,
                status=ClaimStatus.PARTIALLY_SUPPORTED,
                confidence=0.55,
            )
        )
        if "store_claim" in tools:
            tools["store_claim"](state, claim)
        return SkillOutput(
            summary=text,
            claims=[claim],
            confidence=0.55,
            artifacts={"financials": financials},
        )


class HistoricalFinancialAnalysisHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        fetch_financials = tools.get("financial_statement_fetch")
        financials = fetch_financials(ticker) if fetch_financials else {}
        claim = claim_to_dict(
            Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id="historical_financials",
                section_id="5_historical_financials",
                claim_type=ClaimType.DESCRIPTIVE,
                text=f"Historical financial snapshot for {ticker}",
                status=ClaimStatus.PARTIALLY_SUPPORTED,
                confidence=0.6,
            )
        )
        if "store_claim" in tools:
            tools["store_claim"](state, claim)
        return SkillOutput(
            summary=json.dumps(financials, default=str)[:1500],
            claims=[claim],
            confidence=0.6,
            artifacts={"historical_financials": financials},
        )


class ValuationHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        current_price = float(state.get("current_price") or 0)
        if current_price <= 0:
            quote_fn = tools.get("stock_quote")
            if quote_fn:
                quote = quote_fn(ticker)
                if isinstance(quote, dict):
                    current_price = float(
                        quote.get("current_price")
                        or quote.get("price")
                        or quote.get("regularMarketPrice")
                        or 0
                    )
                else:
                    try:
                        current_price = float(str(quote).split()[-1].replace(",", "").replace("$", ""))
                    except (ValueError, IndexError):
                        current_price = 0.0
        result = tools["calculate_trading_multiple_valuation"](
            ticker,
            current_price,
            state.get("forecast_model"),
            state.get("structured_facts", []),
        )
        claim = claim_to_dict(
            Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id="valuation",
                section_id="7_valuation",
                claim_type=ClaimType.VALUATION,
                text=f"Valuation target {result.get('target_price')} ({result.get('rating')})",
                status=ClaimStatus.VERIFIED,
                confidence=0.7,
            )
        )
        if "store_claim" in tools:
            tools["store_claim"](state, claim)
        return SkillOutput(
            summary=json.dumps(result, default=str),
            claims=[claim],
            confidence=0.7,
            artifacts={"valuation_model": result},
        )


class RiskCounterThesisHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        contradictions = (
            tools["retrieve_contradictory_evidence"](state)
            if "retrieve_contradictory_evidence" in tools
            else state.get("contradiction_fragments", [])
        )
        risk_map = []
        claims = []
        for idx, fragment in enumerate(contradictions[:5]):
            thesis = state.get("thesis_ledger", [{}])[0] if state.get("thesis_ledger") else {}
            risk_map.append(
                {
                    "thesis": thesis.get("statement", "core thesis"),
                    "key_risk": fragment.get("text", fragment.get("quote", f"risk_{idx}")),
                    "evidence_to_monitor": fragment.get("metric", "monitor KPI"),
                }
            )
            claim = claim_to_dict(
                Claim(
                    claim_id=str(uuid.uuid4()),
                    hypothesis_id="risk",
                    section_id="9_risks",
                    claim_type=ClaimType.RISK,
                    text=fragment.get("text", fragment.get("quote", "")),
                    status=ClaimStatus.PARTIALLY_SUPPORTED,
                    confidence=0.5,
                )
            )
            claims.append(claim)
            if "store_claim" in tools:
                tools["store_claim"](state, claim)
        return SkillOutput(
            summary=f"Identified {len(risk_map)} risk-to-thesis mappings",
            claims=claims,
            confidence=0.55,
            artifacts={"risk_map": risk_map},
        )


class SectionWritingHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        section_id = input.constraints.get("section_id", "") if input.constraints else ""
        claims = (
            tools["retrieve_claims_by_section"](input.state_snapshot, section_id)
            if "retrieve_claims_by_section" in tools
            else []
        )
        return SkillOutput(
            summary=f"Prepared writing context for {section_id} with {len(claims)} claims",
            claims=claims,
            confidence=0.7,
        )


class DynamicResearchPlanningHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        iterations = int(state.get("research_iterations", 0))
        max_iter = int(state.get("max_research_iterations", 5))
        stage = "convergence" if iterations >= max_iter * 0.8 else "thesis_discovery"
        return SkillOutput(
            summary=f"Planning stage: {stage}",
            confidence=0.7,
            artifacts={"research_strategy": {"stage": stage, "skills_to_run": ["variant_view_discovery"]}},
        )


class ThesisExplorationDAGHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        graph = init_research_graph_from_gaps(state.get("expectation_gaps", []))
        return SkillOutput(
            summary=f"Initialized {len(graph.get('branches', {}))} thesis branches",
            confidence=0.8,
            artifacts={"research_graph": graph},
        )


class ScientificInvestmentReasoningHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        return SkillOutput(
            summary="Scientific reasoning delegated to research loop",
            confidence=0.5,
            next_questions=[input.objective] if input.objective else [],
        )


class CollaborativeMemoryHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        graph = state.get("research_graph", {})
        parents = list(graph.get("nodes", {}).keys())[:2]
        ctx = build_memory_context(state, parents)
        return SkillOutput(
            summary=f"Retrieved {len(ctx.get('evidence', []))} evidence, {len(ctx.get('claims', []))} claims",
            confidence=0.6,
            artifacts={"memory_context": ctx},
        )


class IndustryAnalysisHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        industry = state.get("industry", state.get("sector", ""))
        news = ""
        if "news_search" in tools:
            news_result = tools["news_search"](f"{ticker} {industry} industry competition")
            news = json.dumps(news_result, default=str)[:500]
        text = f"Industry analysis for {ticker} in {industry}: competitive dynamics review."
        claim = claim_to_dict(
            Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id="industry",
                section_id="4_industry_and_competition",
                claim_type=ClaimType.INDUSTRY,
                text=text,
                status=ClaimStatus.PARTIALLY_SUPPORTED,
                confidence=0.55,
            )
        )
        if "store_claim" in tools:
            tools["store_claim"](state, claim)
        return SkillOutput(summary=text[:500], claims=[claim], confidence=0.55, artifacts={"news_snippet": str(news)[:500]})


class ForecastAssumptionBuilderHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        drivers = state.get("business_drivers", [])
        assumptions = []
        for driver in drivers[:5]:
            assumptions.append({
                "assumption_id": f"asm_{uuid.uuid4().hex[:8]}",
                "metric": driver.get("metric_link", "revenue"),
                "our_assumption": driver.get("assumption", driver.get("driver_name", "")),
                "rationale": driver.get("driver_name", ""),
                "used_in": ["financial_forecast"],
            })
        if not assumptions:
            assumptions = [{
                "assumption_id": f"asm_{uuid.uuid4().hex[:8]}",
                "metric": "revenue_growth",
                "our_assumption": "10%",
                "rationale": "default assumption",
            }]
        if "store_assumption" in tools:
            for assumption in assumptions:
                tools["store_assumption"](state, assumption)
        return SkillOutput(
            summary=f"Built {len(assumptions)} forecast assumptions",
            confidence=0.65,
            assumptions=assumptions,
            artifacts={"model_assumptions": assumptions},
        )


class CatalystMonitoringHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        gaps = state.get("expectation_gaps", [])
        calendar = [
            {
                "catalyst_id": str(uuid.uuid4()),
                "description": g.get("description", ""),
                "timeframe": "medium_term",
            }
            for g in gaps[:5]
        ]
        if "earnings_calendar" in tools:
            earnings = tools["earnings_calendar"](ticker)
            calendar.append({
                "catalyst_id": str(uuid.uuid4()),
                "description": f"Next earnings release: {json.dumps(earnings, default=str)[:200]}",
                "timeframe": "near_term",
            })
        else:
            calendar.append({
                "catalyst_id": str(uuid.uuid4()),
                "description": "Next earnings release",
                "timeframe": "near_term",
            })
        return SkillOutput(
            summary=f"Built catalyst calendar with {len(calendar)} items",
            confidence=0.7,
            artifacts={"catalyst_calendar": calendar},
        )


class StandardizedQAHandler:  # LEGACY: not loaded at runtime
    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        result = aggregate_ic_scores(state)
        flags = result.blocking_issues + result.warnings
        return SkillOutput(
            summary=f"QA score: {result.aggregate_score:.2f}, issues: {len(flags)}",
            confidence=result.aggregate_score,
            data_quality_flags=flags,
            artifacts={"evaluation": result.dimension_scores},
        )
