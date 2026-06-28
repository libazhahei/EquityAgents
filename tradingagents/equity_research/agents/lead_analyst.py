"""Lead Analyst Agent for Equity R&D-Agent orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from tradingagents.equity_research.agents.domain import (
    BusinessAnalystAgent,
    ConsensusAnalystAgent,
    EvidenceAnalystAgent,
    ForecastAgent,
    IndustryAnalystAgent,
    RiskAgent,
    ValuationAgent,
)
from tradingagents.equity_research.evaluation.aggregators import aggregate_thesis_score
from tradingagents.equity_research.prompts.rd_agent import dynamic_planning_prompt
from tradingagents.equity_research.state.consensus_schemas import get_consensus_view_for_prompt
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.tools.registry import ToolRegistry

AGENT_SKILL_MAP = {
    "consensus": ConsensusAnalystAgent,
    "evidence": EvidenceAnalystAgent,
    "business": BusinessAnalystAgent,
    "industry": IndustryAnalystAgent,
    "forecast": ForecastAgent,
    "valuation": ValuationAgent,
    "risk": RiskAgent,
}


@dataclass
class ResearchCritique:
    next_status: str
    remaining_gaps: list[dict]
    is_sufficient: bool
    aggregate_score: float = 0.0


class LeadAnalystAgent:
    def __init__(self, skill_registry: SkillRegistry, deps: Any):
        self.skill_registry = skill_registry
        self.deps = deps
        self.tool_registry = ToolRegistry(deps)
        self._agents = {
            name: cls(skill_registry, self.tool_registry)
            for name, cls in AGENT_SKILL_MAP.items()
        }

    def plan_next_iteration(self, state: dict[str, Any]) -> dict[str, Any]:
        existing = state.get("research_strategy", {})
        if existing.get("stage"):
            return existing
        try:
            prompt = dynamic_planning_prompt(state)
            response = self.deps.quick_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            import re
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        iterations = int(state.get("research_iterations", 0))
        max_iter = int(state.get("max_research_iterations", 5))
        stage = "convergence" if iterations >= max_iter * 0.8 else "thesis_discovery"
        return {
            "stage": stage,
            "skills_to_run": ["variant_view_discovery"],
            "agents_to_dispatch": ["consensus", "business"],
        }

    def dispatch_development(self, state: dict[str, Any], strategy: dict[str, Any]) -> dict[str, Any]:
        updates: dict[str, Any] = {"claims": list(state.get("claims", []))}
        agents = strategy.get("agents_to_dispatch", [])
        objective = state.get("active_objective", "")
        for agent_name in agents:
            agent = self._agents.get(agent_name)
            if not agent:
                continue
            output = agent.run(state, objective)
            updates["claims"] = updates.get("claims", []) + output.claims
            if output.artifacts.get("valuation_model"):
                updates["valuation_model"] = output.artifacts["valuation_model"]
            if output.artifacts.get("historical_financials"):
                updates["historical_financials"] = output.artifacts["historical_financials"]
            if output.artifacts.get("risk_map"):
                updates["risk_map"] = output.artifacts["risk_map"]
        return updates

    def pick_next_research_objective(self, state: dict[str, Any]) -> str:
        strategy = self.plan_next_iteration(state)
        questions = strategy.get("priority_questions", [])
        if questions:
            return questions[0]
        plan = state.get("research_plan", {})
        completed = set(state.get("completed_objectives", []))
        for question in plan.get("core_questions", []):
            if question.get("id") not in completed and question.get("status") != "done":
                return question.get("question", question.get("id", "variant_view"))
        gaps = state.get("research_gaps", [])
        if gaps:
            return gaps[0].get("description", "variant_view")
        graph = state.get("research_graph", {})
        best_id = graph.get("best_node_id")
        if best_id:
            node = graph.get("nodes", {}).get(best_id, {})
            return node.get("thesis", "business_model and revenue drivers")
        return "variant_view discovery for investment thesis"

    def select_skill(self, objective: str, state: dict[str, Any]) -> str:
        strategy = state.get("research_strategy", {})
        skills = strategy.get("skills_to_run", [])
        if skills:
            return skills[0]
        plan = state.get("research_plan", {})
        for question in plan.get("core_questions", []):
            if question.get("question") == objective and question.get("required_skills"):
                return question["required_skills"][0]
        return self.skill_registry.select_for_objective(objective)

    def critique_research_output(
        self,
        objective: str,
        output: Any,
        state: dict[str, Any],
    ) -> ResearchCritique:
        iterations = int(state.get("research_iterations", 0))
        max_iterations = int(state.get("max_research_iterations", 5))
        graph = state.get("research_graph", {})
        best_id = graph.get("best_node_id")
        best_score = 0.0
        if best_id:
            best_score = float(graph.get("nodes", {}).get(best_id, {}).get("real_score") or 0)

        artifacts = {"evidence_ids": [e.get("evidence_id") for e in state.get("evidence_ledger", [])]}
        evaluation = aggregate_thesis_score(state, artifacts)
        threshold = float(self.deps.config.get("equity_research", {}).get("thesis_score_threshold", 0.55))

        if best_score >= threshold and state.get("research_strategy", {}).get("stage") == "convergence":
            return ResearchCritique("sufficient", [], True, best_score)
        if iterations >= max_iterations:
            return ResearchCritique("sufficient", state.get("research_gaps", []), True, best_score)
        if best_score >= threshold and len(graph.get("nodes", {})) >= 3:
            return ResearchCritique("sufficient", [], True, best_score)

        remaining = [{"description": q} for q in getattr(output, "next_questions", [])[:2]]
        if not remaining:
            remaining = [{"description": f"More evidence needed for: {objective}"}]
        return ResearchCritique("continue", remaining, False, evaluation.aggregate_score)

    def generate_research_plan_prompt(self, state: dict[str, Any]) -> str:
        gaps = json.dumps(state.get("expectation_gaps", [])[:4], default=str)
        consensus = get_consensus_view_for_prompt(state)
        return (
            f"Create a thesis-driven research plan for {state.get('ticker')}.\n"
            f"Consensus: {consensus}\nExpectation gaps: {gaps}\n"
            "Return JSON with core_questions array. Each item: id, question, priority, "
            "linked_sections, required_skills, success_criteria."
        )
