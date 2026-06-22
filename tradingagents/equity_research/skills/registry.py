"""Skill registry for equity research."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.skills.base import Skill
from tradingagents.equity_research.skills.implementations import (
    BrokerConsensusMiningSkill,
    BusinessModelAnalysisSkill,
    CatalystMonitoringSkill,
    CollaborativeMemorySkill,
    DynamicResearchPlanningSkill,
    ForecastAssumptionBuilderSkill,
    HistoricalFinancialAnalysisSkill,
    IndustryAnalysisSkill,
    RiskCounterThesisSkill,
    ScientificInvestmentReasoningSkill,
    SectionWritingSkill,
    StandardizedQASkill,
    ThesisExplorationDAGSkill,
    ValuationSkill,
    VariantViewDiscoverySkill,
)


OBJECTIVE_SKILL_MAP = {
    "consensus": "broker_consensus_mining",
    "variant_view": "variant_view_discovery",
    "business_model": "business_model_analysis",
    "historical_financials": "historical_financial_analysis",
    "valuation": "valuation",
    "risk": "risk_counterthesis",
    "company_overview": "business_model_analysis",
    "industry": "industry_analysis",
    "planning": "dynamic_research_planning",
    "thesis": "thesis_exploration_dag",
    "reasoning": "scientific_investment_reasoning",
    "memory": "collaborative_memory",
    "forecast": "forecast_assumption_builder",
    "catalyst": "catalyst_monitoring",
    "qa": "standardized_qa",
    "default": "variant_view_discovery",
}


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        for skill in [
            DynamicResearchPlanningSkill(),
            ThesisExplorationDAGSkill(),
            ScientificInvestmentReasoningSkill(),
            CollaborativeMemorySkill(),
            BrokerConsensusMiningSkill(),
            VariantViewDiscoverySkill(),
            BusinessModelAnalysisSkill(),
            IndustryAnalysisSkill(),
            HistoricalFinancialAnalysisSkill(),
            ForecastAssumptionBuilderSkill(),
            ValuationSkill(),
            RiskCounterThesisSkill(),
            CatalystMonitoringSkill(),
            StandardizedQASkill(),
            SectionWritingSkill(),
        ]:
            self.register(skill)

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def list(self) -> list[str]:
        return list(self._skills.keys())

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"Skill '{name}' not registered")
        return self._skills[name]

    def select_for_objective(self, objective: str) -> str:
        objective_lower = objective.lower()
        for key, skill_name in OBJECTIVE_SKILL_MAP.items():
            if key in objective_lower:
                return skill_name
        return OBJECTIVE_SKILL_MAP["default"]

    def manifests(self) -> list[dict]:
        return [s.manifest.model_dump() for s in self._skills.values()]
