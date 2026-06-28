"""Dynamic research planning node."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.lead_analyst import LeadAnalystAgent
from tradingagents.equity_research.prompts.rd_agent import dynamic_planning_prompt
from tradingagents.equity_research.skills.catalog import format_catalog_for_prompt
from tradingagents.equity_research.skills.registry import SkillRegistry


from tradingagents.equity_research.tools.registry import ToolRegistry


def _skill_registry(deps: EquityResearchDeps) -> SkillRegistry:
    tools = ToolRegistry(deps)
    return SkillRegistry(deps=deps, known_tools=set(tools.list_tools()), config=deps.config)


def create_dynamic_planning(deps: EquityResearchDeps):
    def dynamic_planning(state: dict[str, Any]) -> dict[str, Any]:
        agent = LeadAnalystAgent(_skill_registry(deps), deps)
        try:
            registry = _skill_registry(deps)
            eligible = registry.get_eligible_catalog("dynamic_planning")
            catalog_block = format_catalog_for_prompt(eligible)
            prompt = (
                f"{dynamic_planning_prompt(state)}\n\n"
                f"Eligible skill catalog:\n{catalog_block}\n"
            )
            response = deps.quick_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                strategy = json.loads(match.group())
            else:
                strategy = agent.plan_next_iteration(state)
        except Exception:
            strategy = agent.plan_next_iteration(state)

        updates = {
            "research_strategy": strategy,
            "research_phase": strategy.get("stage", state.get("research_phase", "early")),
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "dynamic_planning", {"stage": strategy.get("stage")}))
        return updates

    return dynamic_planning
