"""Workflow spine agents: mandate, ingestion, research plan, gates."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.equity_research_state import EquityResearchState
from tradingagents.equity_research.state.ledgers import ResearchMandate, ResearchPlan, ResearchPlanQuestion
from tradingagents.equity_research.tools.data_retrieval import get_financial_statements


def create_define_research_mandate(deps: EquityResearchDeps):
    def define_research_mandate(state: dict[str, Any]) -> dict[str, Any]:
        mandate = ResearchMandate(
            ticker=state.get("ticker", ""),
            report_type=state.get("report_type", "initiation"),
            time_horizon=state.get("time_horizon", "12m"),
            currency=state.get("currency", "USD"),
            allow_broker_reports=True,
        )
        updates = {
            "mandate": mandate.model_dump(),
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "define_research_mandate"))
        return updates

    return define_research_mandate


def create_ingest_documents(deps: EquityResearchDeps):
    def ingest_documents(state: EquityResearchState) -> dict[str, Any]:
        ticker = state.get("ticker", "")
        documents = list(state.get("documents", []))
        for filing in deps.edgar.fetch_recent_filings(ticker)[:3]:
            doc = deps.documents.register(
                ticker=ticker,
                source_type=filing.get("form", "10-K"),
                title=f"{ticker} {filing.get('form', '')}",
                source_url=filing.get("url", ""),
                published_date=filing.get("filing_date"),
            )
            documents.append(doc)
        updates = {
            "documents": documents,
            "api_calls": state.get("api_calls", 0) + 1,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "ingest_documents"))
        return updates

    return ingest_documents


def create_build_source_index(deps: EquityResearchDeps):
    def build_source_index(state: dict[str, Any]) -> dict[str, Any]:
        source_index = []
        for idx, doc in enumerate(state.get("documents", [])):
            source_index.append({
                "source_id": f"SRC_{idx + 1:03d}",
                "source_type": doc.get("source_type", "document"),
                "title": doc.get("title", ""),
                "date": doc.get("published_date", ""),
                "publisher": doc.get("publisher", "unknown"),
                "reliability": 0.9 if doc.get("source_type") in ("10-K", "10-Q") else 0.6,
                "doc_id": doc.get("doc_id", ""),
            })
        updates = {
            "source_index": source_index,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "build_source_index"))
        return updates

    return build_source_index


def create_extract_broker_views(deps: EquityResearchDeps):
    def extract_broker_views(state: dict[str, Any]) -> dict[str, Any]:
        from tradingagents.llm_clients.perplexity_client import SearchMode

        ticker = state["ticker"]
        result = {"answer": "", "citations": []}
        if deps.perplexity.api_key:
            result = deps.perplexity.search(
                f"{ticker} analyst ratings price targets broker reports",
                mode=SearchMode.EXPLORATORY,
            )
        broker_views = [{
            "view_id": str(uuid.uuid4()),
            "summary": result.get("answer", "")[:3000],
            "citations": result.get("citations", [])[:10],
        }]
        updates = {
            "broker_views": broker_views,
            "api_calls": state.get("api_calls", 0) + 1,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "extract_broker_views"))
        return updates

    return extract_broker_views


def create_generate_research_plan(deps: EquityResearchDeps):
    def generate_research_plan(state: dict[str, Any]) -> dict[str, Any]:
        from tradingagents.equity_research.agents.lead_analyst import LeadAnalystAgent
        from tradingagents.equity_research.skills.registry import SkillRegistry

        agent = LeadAnalystAgent(SkillRegistry(), deps)
        prompt = agent.generate_research_plan_prompt(state)
        response = deps.deep_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        questions = _parse_research_questions(text)
        if not questions:
            questions = [
                ResearchPlanQuestion(
                    id="Q1",
                    question="Where does our view differ from consensus?",
                    priority="high",
                    linked_sections=["1_investment_summary"],
                    required_skills=["variant_view_discovery"],
                ),
                ResearchPlanQuestion(
                    id="Q2",
                    question="What drives revenue and margin?",
                    priority="high",
                    linked_sections=["3_business_model", "6_earnings_forecast"],
                    required_skills=["business_model_analysis"],
                ),
            ]
        plan = ResearchPlan(core_questions=questions)
        updates = {
            "research_plan": plan.model_dump(),
            "research_status": "continue",
            "research_iterations": 0,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "generate_research_plan"))
        return updates

    return generate_research_plan


def create_historical_financials(deps: EquityResearchDeps):
    def historical_financials(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        data = get_financial_statements(ticker)
        updates = {
            "historical_financials": data,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "historical_financials"))
        return updates

    return historical_financials


def create_operating_kpi_extraction(deps: EquityResearchDeps):
    def operating_kpi_extraction(state: dict[str, Any]) -> dict[str, Any]:
        facts = state.get("structured_facts", [])
        kpis = {}
        for fact in facts:
            name = fact.get("metric_name", "").lower()
            if name:
                kpis[name] = fact.get("metric_value")
        if not kpis and state.get("historical_financials"):
            kpis["snapshot"] = str(state["historical_financials"])[:500]
        updates = {
            "operating_kpis": kpis,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "operating_kpi_extraction"))
        return updates

    return operating_kpi_extraction


def create_forecast_consistency_check(deps: EquityResearchDeps):
    def forecast_consistency_check(state: dict[str, Any]) -> dict[str, Any]:
        model = state.get("forecast_model") or {}
        assumptions = state.get("model_assumptions", [])
        issues = []
        if not model.get("eps_forecast_3y"):
            issues.append("missing_eps_forecast")
        if not assumptions:
            issues.append("forecast_assumptions_lack_citations")
        route = "pass" if not issues else "revise_assumptions"
        if not model and issues:
            route = "more_research"
        updates = {
            "next_route": route,
            "review_findings": state.get("review_findings", []) + issues,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "forecast_consistency_check", {"route": route}))
        return updates

    return forecast_consistency_check


def create_scenario_sensitivity(deps: EquityResearchDeps):
    def scenario_sensitivity(state: dict[str, Any]) -> dict[str, Any]:
        from tradingagents.equity_research.tools.calculators import calculate_sensitivity_table

        base_tp = float(state.get("target_price") or 0)
        scenarios = [
            {"name": "bull", "assumptions": "revenue CAGR 20%, margin expansion", "target_multiplier": 1.25},
            {"name": "base", "assumptions": "consensus growth, stable margin", "target_multiplier": 1.0},
            {"name": "bear", "assumptions": "growth slowdown, margin compression", "target_multiplier": 0.75},
        ]
        table = calculate_sensitivity_table(base_tp, scenarios) if base_tp else []
        scenario_analysis = {
            "bull_case_assumptions": scenarios[0]["assumptions"],
            "base_case_assumptions": scenarios[1]["assumptions"],
            "bear_case_assumptions": scenarios[2]["assumptions"],
            "target_price_range": [r.get("implied_target_price") for r in table],
            "valuation_sensitivity_table": table,
        }
        updates = {
            "scenario_analysis": scenario_analysis,
            "sensitivity_results": table,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "scenario_sensitivity"))
        return updates

    return scenario_sensitivity


def create_rating_target_price_check(deps: EquityResearchDeps):
    def rating_target_price_check(state: dict[str, Any]) -> dict[str, Any]:
        from tradingagents.equity_research.computation.valuation_mock import check_rating_upside_consistency

        rating = state.get("rating")
        target_price = state.get("target_price")
        current_price = float(state.get("current_price") or 0)
        dividend_yield = float(state.get("dividend_yield_pct") or 0)
        upside = 0.0
        if current_price > 0 and target_price:
            upside = (float(target_price) - current_price) / current_price
        issues = []
        if not rating:
            issues.append("rating_missing")
        if not target_price:
            issues.append("target_price_missing")
        if rating:
            issues.extend(check_rating_upside_consistency(rating, upside, dividend_yield))
        route = "pass" if not issues else "revise_valuation"
        updates = {
            "next_route": route,
            "review_findings": state.get("review_findings", []) + issues,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "rating_target_price_check", {"route": route}))
        return updates

    return rating_target_price_check


def create_risk_to_thesis_mapping(deps: EquityResearchDeps):
    def risk_to_thesis_mapping(state: dict[str, Any]) -> dict[str, Any]:
        from tradingagents.equity_research.skills.implementations import RiskCounterThesisSkill
        from tradingagents.equity_research.skills.base import SkillInput
        from tradingagents.equity_research.tools.registry import ToolRegistry

        skill = RiskCounterThesisSkill()
        tools = ToolRegistry(deps).for_skill(skill.manifest.allowed_tools)
        output = skill.run(SkillInput(state_snapshot=state, objective="risk mapping"), tools)
        updates = {
            "risk_map": output.artifacts.get("risk_map", []),
            "claims": state.get("claims", []) + output.claims,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "risk_to_thesis_mapping"))
        return updates

    return risk_to_thesis_mapping


def create_catalyst_monitor(deps: EquityResearchDeps):
    def catalyst_monitor(state: dict[str, Any]) -> dict[str, Any]:
        gaps = state.get("expectation_gaps", [])
        calendar = [
            {
                "catalyst_id": str(uuid.uuid4()),
                "description": g.get("description", ""),
                "timeframe": "medium_term",
                "thesis_link": g.get("alpha_source", ""),
            }
            for g in gaps[:5]
        ]
        calendar.append({
            "catalyst_id": str(uuid.uuid4()),
            "description": "Next earnings release",
            "timeframe": "near_term",
            "thesis_link": "earnings validation",
        })
        updates = {
            "catalyst_calendar": calendar,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "catalyst_monitor"))
        return updates

    return catalyst_monitor


def create_final_consistency_check(deps: EquityResearchDeps):
    def final_consistency_check(state: dict[str, Any]) -> dict[str, Any]:
        issues = []
        if not state.get("final_report"):
            issues.append("missing_final_report")
        draft = state.get("section_drafts", {}).get("1_investment_summary", {})
        completed = draft.get("completed_outputs", [])
        if "variant_view" not in completed and draft:
            issues.append("no_variant_view")
        updates = {
            "review_findings": state.get("review_findings", []) + issues,
            "next_route": "pass" if not issues else "fail",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "final_consistency_check"))
        return updates

    return final_consistency_check


def create_compliance_check(deps: EquityResearchDeps):
    def compliance_check(state: dict[str, Any]) -> dict[str, Any]:
        flags = [{"type": "disclaimer_required", "message": "Research report requires compliance disclaimer"}]
        updates = {
            "compliance_flags": flags,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "compliance_check"))
        return updates

    return compliance_check


def create_plan_tables_and_charts(deps: EquityResearchDeps):
    def plan_tables_and_charts(state: dict[str, Any]) -> dict[str, Any]:
        placeholders = list(state.get("chart_placeholders", []))
        if not placeholders:
            placeholders = [{
                "chart_id": str(uuid.uuid4()),
                "title": f"{state['ticker']} Revenue & Margin Trend",
                "planned": True,
            }]
        updates = {
            "chart_placeholders": placeholders,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "plan_tables_and_charts"))
        return updates

    return plan_tables_and_charts


def _parse_research_questions(text: str) -> list[ResearchPlanQuestion]:
    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            items = data.get("core_questions", data if isinstance(data, list) else [])
            return [
                ResearchPlanQuestion(
                    id=item.get("id", f"Q{i}"),
                    question=item.get("question", ""),
                    priority=item.get("priority", "medium"),
                    linked_sections=item.get("linked_sections", []),
                    required_skills=item.get("required_skills", []),
                    success_criteria=item.get("success_criteria", []),
                )
                for i, item in enumerate(items[:6])
            ]
    except (json.JSONDecodeError, ValueError):
        pass
    return []
