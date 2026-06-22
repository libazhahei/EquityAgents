"""Base domain agent."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.skills.base import SkillInput, SkillOutput
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.tools.registry import ToolRegistry


class BaseDomainAgent:
    skill_names: list[str] = []

    def __init__(self, skill_registry: SkillRegistry, tool_registry: ToolRegistry):
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry

    def run(self, state: dict[str, Any], objective: str = "") -> SkillOutput:
        combined = SkillOutput()
        for name in self.skill_names:
            try:
                skill = self.skill_registry.get(name)
                tools = self.tool_registry.for_skill(skill.manifest.allowed_tools)
                output = skill.run(
                    SkillInput(
                        mandate=state.get("mandate", {}),
                        state_snapshot=state,
                        objective=objective,
                    ),
                    tools,
                )
                combined.summary += output.summary + " "
                combined.claims.extend(output.claims)
                combined.confidence = max(combined.confidence, output.confidence)
                combined.artifacts.update(output.artifacts)
            except KeyError:
                continue
        return combined
