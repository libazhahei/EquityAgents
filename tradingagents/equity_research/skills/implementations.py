"""Concrete skill implementations for equity research."""

from __future__ import annotations

import json
import uuid
from typing import Any

from tradingagents.equity_research.skills.base import SkillInput, SkillManifest, SkillOutput
from tradingagents.equity_research.state.schemas import ClaimStatus, ClaimType, claim_to_dict, Claim


class BrokerConsensusMiningSkill:
    name = "broker_consensus_mining"
    manifest = SkillManifest(
        name=name,
        description="Extract and compare sell-side broker views.",
        allowed_tools=["get_consensus_estimates", "get_news", "store_evidence", "store_claim"],
        quality_gates=["source citation required"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        consensus_data = tools["get_consensus_estimates"](ticker) if "get_consensus_estimates" in tools else {}
        summary = json.dumps(consensus_data, default=str)[:2000]
        claim = claim_to_dict(
            Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id="consensus",
                section_id="1_investment_summary",
                claim_type=ClaimType.RECOMMENDATION,
                text=f"Broker consensus snapshot for {ticker}: {summary[:500]}",
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


class VariantViewDiscoverySkill:
    name = "variant_view_discovery"
    manifest = SkillManifest(
        name=name,
        description="Identify where our view differs from consensus.",
        allowed_tools=["retrieve_claims_by_section", "store_claim"],
        quality_gates=["must articulate variant view"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
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


class BusinessModelAnalysisSkill:
    name = "business_model_analysis"
    manifest = SkillManifest(
        name=name,
        description="Analyze business model and revenue drivers.",
        allowed_tools=["get_financial_statements", "store_claim", "store_evidence"],
        quality_gates=["at least 2 revenue drivers"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        financials = tools["get_financial_statements"](ticker) if "get_financial_statements" in tools else {}
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


class HistoricalFinancialAnalysisSkill:
    name = "historical_financial_analysis"
    manifest = SkillManifest(
        name=name,
        description="Analyze historical financial performance.",
        allowed_tools=["get_financial_statements", "calculate_cagr", "store_claim"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        financials = tools["get_financial_statements"](ticker) if "get_financial_statements" in tools else {}
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


class ValuationSkill:
    name = "valuation"
    manifest = SkillManifest(
        name=name,
        description="Deterministic valuation via trading multiples.",
        allowed_tools=["calculate_trading_multiple_valuation", "get_current_price", "store_claim"],
        quality_gates=["target price must come from calculator"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        result = tools["calculate_trading_multiple_valuation"](
            ticker,
            float(state.get("current_price") or 0),
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


class RiskCounterThesisSkill:
    name = "risk_counterthesis"
    manifest = SkillManifest(
        name=name,
        description="Map risks to thesis and find counter-evidence.",
        allowed_tools=["retrieve_contradictory_evidence", "store_claim"],
        quality_gates=["each core thesis must have mapped risk"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
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


class SectionWritingSkill:
    name = "section_writing"
    manifest = SkillManifest(
        name=name,
        description="Write a report section from verified claims.",
        allowed_tools=["retrieve_claims_by_section"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
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


class StubSkill:
    """Placeholder skill registered for future implementation."""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.manifest = SkillManifest(name=name, description=description)

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        return SkillOutput(
            summary=f"Stub skill {self.name} — no implementation yet",
            confidence=0.0,
            data_quality_flags=["stub_skill"],
        )


class DynamicResearchPlanningSkill:
    name = "dynamic_research_planning"
    manifest = SkillManifest(
        name=name,
        description="Dynamic stage-aware research planning.",
        allowed_tools=[],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        iterations = int(state.get("research_iterations", 0))
        max_iter = int(state.get("max_research_iterations", 5))
        stage = "convergence" if iterations >= max_iter * 0.8 else "thesis_discovery"
        return SkillOutput(
            summary=f"Planning stage: {stage}",
            confidence=0.7,
            artifacts={"research_strategy": {"stage": stage, "skills_to_run": ["variant_view_discovery"]}},
        )


class ThesisExplorationDAGSkill:
    name = "thesis_exploration_dag"
    manifest = SkillManifest(name=name, description="Initialize and extend thesis exploration branches.")

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        from tradingagents.equity_research.state.research_graph import init_research_graph_from_gaps

        state = input.state_snapshot
        graph = init_research_graph_from_gaps(state.get("expectation_gaps", []))
        return SkillOutput(
            summary=f"Initialized {len(graph.get('branches', {}))} thesis branches",
            confidence=0.8,
            artifacts={"research_graph": graph},
        )


class ScientificInvestmentReasoningSkill:
    name = "scientific_investment_reasoning"
    manifest = SkillManifest(name=name, description="Scientific multi-step investment hypothesis generation.")

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        return SkillOutput(
            summary="Scientific reasoning delegated to research loop",
            confidence=0.5,
            next_questions=[input.objective] if input.objective else [],
        )


class CollaborativeMemorySkill:
    name = "collaborative_memory"
    manifest = SkillManifest(name=name, description="Cross-branch collaborative memory retrieval.")

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        from tradingagents.equity_research.memory.retrieval import build_memory_context

        state = input.state_snapshot
        graph = state.get("research_graph", {})
        parents = list(graph.get("nodes", {}).keys())[:2]
        ctx = build_memory_context(state, parents)
        return SkillOutput(
            summary=f"Retrieved {len(ctx.get('evidence', []))} evidence, {len(ctx.get('claims', []))} claims",
            confidence=0.6,
            artifacts={"memory_context": ctx},
        )


class IndustryAnalysisSkill:
    name = "industry_analysis"
    manifest = SkillManifest(
        name=name,
        description="Industry and competitive landscape analysis.",
        allowed_tools=["get_news", "store_claim", "store_evidence"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        ticker = state.get("ticker", "")
        industry = state.get("industry", state.get("sector", ""))
        news = tools["get_news"](ticker) if "get_news" in tools else ""
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


class ForecastAssumptionBuilderSkill:
    name = "forecast_assumption_builder"
    manifest = SkillManifest(
        name=name,
        description="Build forecast assumptions from business drivers and claims.",
        allowed_tools=["store_claim"],
    )

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        drivers = state.get("business_drivers", [])
        assumptions = []
        for idx, driver in enumerate(drivers[:5]):
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
        return SkillOutput(
            summary=f"Built {len(assumptions)} forecast assumptions",
            confidence=0.65,
            assumptions=assumptions,
            artifacts={"model_assumptions": assumptions},
        )


class CatalystMonitoringSkill:
    name = "catalyst_monitoring"
    manifest = SkillManifest(name=name, description="Build catalyst calendar from gaps and earnings.")

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        gaps = state.get("expectation_gaps", [])
        calendar = [
            {
                "catalyst_id": str(uuid.uuid4()),
                "description": g.get("description", ""),
                "timeframe": "medium_term",
            }
            for g in gaps[:5]
        ]
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


class StandardizedQASkill:
    name = "standardized_qa"
    manifest = SkillManifest(name=name, description="Standardized quality assessment.")

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        from tradingagents.equity_research.evaluation.aggregators import aggregate_ic_scores

        state = input.state_snapshot
        result = aggregate_ic_scores(state)
        flags = result.blocking_issues + result.warnings
        return SkillOutput(
            summary=f"QA score: {result.aggregate_score:.2f}, issues: {len(flags)}",
            confidence=result.aggregate_score,
            data_quality_flags=flags,
            artifacts={"evaluation": result.dimension_scores},
        )
