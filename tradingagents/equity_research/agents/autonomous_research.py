"""Autonomous research runtime — encapsulates hypothesis/evidence loop and skills."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.lead_analyst import LeadAnalystAgent
from tradingagents.equity_research.agents.hypothesis_agents import (
    create_allocate_budget,
    create_generate_hypotheses,
    create_virtual_evaluate,
)
from tradingagents.equity_research.agents.evidence_agents import (
    create_evaluate_stop_condition,
    create_extract_facts,
    create_retrieve_evidence,
    create_verify_claims,
)
from tradingagents.equity_research.skills.base import SkillInput
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy
from tradingagents.equity_research.tools.registry import ToolRegistry


class AutonomousResearchRuntime:
    def __init__(self, deps: EquityResearchDeps):
        self.deps = deps
        self.tool_registry = ToolRegistry(deps)
        self.skill_registry = SkillRegistry()
        self.lead_agent = LeadAnalystAgent(self.skill_registry, deps)
        self._legacy_generate = create_generate_hypotheses(deps)
        self._legacy_evaluate = create_virtual_evaluate(deps)
        self._legacy_budget = create_allocate_budget(deps)
        self._legacy_retrieve = create_retrieve_evidence(deps)
        self._legacy_extract = create_extract_facts(deps)
        self._legacy_verify = create_verify_claims(deps)
        self._legacy_stop = create_evaluate_stop_condition(deps)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        objective = self.lead_agent.pick_next_research_objective(state)
        skill_name = self.lead_agent.select_skill(objective, state)

        try:
            skill = self.skill_registry.get(skill_name)
            tools = self.tool_registry.for_skill(skill.manifest.allowed_tools)
            output = skill.run(
                SkillInput(
                    mandate=state.get("mandate", {}),
                    state_snapshot=state,
                    objective=objective,
                ),
                tools,
            )
            updates = self._apply_skill_output(state, output, objective, skill_name)
        except KeyError:
            updates = self._run_legacy_iteration(state, objective)

        merged = {**state, **updates}
        skill_output = updates.get("_skill_output")
        if skill_output is None:
            from tradingagents.equity_research.skills.base import SkillOutput
            skill_output = SkillOutput(confidence=0.5 if merged.get("claims") else 0.3)
        critique = self.lead_agent.critique_research_output(objective, skill_output, merged)

        iterations = int(state.get("research_iterations", 0)) + 1
        completed = list(state.get("completed_objectives", []))
        objective_id = objective[:32]
        if critique.is_sufficient and objective_id not in completed:
            completed.append(objective_id)

        ledger_sync = sync_ledgers_from_legacy(merged)
        final_updates = {
            **updates,
            **ledger_sync,
            "active_objective": objective,
            "research_status": critique.next_status,
            "research_gaps": critique.remaining_gaps,
            "research_iterations": iterations,
            "completed_objectives": completed,
            "last_updated": datetime.utcnow().isoformat(),
        }
        final_updates.pop("_skill_output", None)
        final_updates.update(self.deps.trace({**state, **final_updates}, "autonomous_research", {
            "objective": objective,
            "skill": skill_name,
            "status": critique.next_status,
        }))
        return final_updates

    def _apply_skill_output(self, state: dict, output, objective: str, skill_name: str) -> dict:
        artifacts = output.artifacts or {}
        updates: dict[str, Any] = {
            "claims": state.get("claims", []) + output.claims,
            "_skill_output": output,
        }
        if artifacts.get("historical_financials"):
            updates["historical_financials"] = artifacts["historical_financials"]
        if artifacts.get("valuation_model"):
            updates["valuation_model"] = artifacts["valuation_model"]
            updates["target_price"] = artifacts["valuation_model"].get("target_price")
            updates["rating"] = artifacts["valuation_model"].get("rating")
        if artifacts.get("risk_map"):
            updates["risk_map"] = artifacts["risk_map"]
        if artifacts.get("consensus_data"):
            updates["broker_views"] = state.get("broker_views", []) + [artifacts["consensus_data"]]
        return updates

    def _run_legacy_iteration(self, state: dict[str, Any], objective: str) -> dict[str, Any]:
        section_map = {
            "variant": "1_investment_summary",
            "business": "3_business_model",
            "historical": "5_historical_financials",
            "industry": "4_industry_and_competition",
            "risk": "9_risks",
        }
        section_id = "2_company_overview"
        obj_lower = objective.lower()
        for key, sid in section_map.items():
            if key in obj_lower:
                section_id = sid
                break

        working = {**state, "active_section_id": section_id}
        working = {**working, **self._legacy_generate(working)}
        working = {**working, **self._legacy_evaluate(working)}
        working = {**working, **self._legacy_budget(working)}
        working = {**working, **self._legacy_retrieve(working)}
        working = {**working, **self._legacy_extract(working)}
        working = {**working, **self._legacy_verify(working)}
        stop = self._legacy_stop(working)
        return {
            "hypothesis_nodes": working.get("hypothesis_nodes", {}),
            "active_hypothesis_ids": working.get("active_hypothesis_ids", []),
            "verified_hypothesis_ids": working.get("verified_hypothesis_ids", []),
            "claims": working.get("claims", []),
            "evidence_fragments": working.get("evidence_fragments", []),
            "contradiction_fragments": working.get("contradiction_fragments", []),
            "structured_facts": working.get("structured_facts", []),
            "documents": working.get("documents", []),
            "research_budget": working.get("research_budget", {}),
            "api_calls": working.get("api_calls", 0),
            "_hypothesis_route": stop.get("_hypothesis_route"),
        }


def create_autonomous_research(deps: EquityResearchDeps):
    runtime = AutonomousResearchRuntime(deps)

    def autonomous_research(state: dict[str, Any]) -> dict[str, Any]:
        return runtime.run(state)

    return autonomous_research
