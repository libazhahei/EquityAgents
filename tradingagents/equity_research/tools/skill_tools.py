"""LangChain tools for skill loading in research subgraphs."""

from __future__ import annotations

import json
from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.skills.registry import SkillRegistry


def make_load_research_skills_tool(
    registry: SkillRegistry,
    *,
    graph_name: str,
    objective: str,
    max_skills: int = 2,
):
    eligible = registry.get_eligible_catalog(graph_name)
    valid_names = {entry.name for entry in eligible}
    catalog_snapshot = [entry.to_prompt_dict() for entry in eligible]
    fallback_name = registry.select_for_objective(objective)

    @tool
    def load_research_skills(
        skill_names: Annotated[
            list[str],
            "Skill names from the catalog to load (max 2)",
        ],
    ) -> str:
        """Load equity research skills by name from the eligible catalog."""
        names = [n for n in skill_names if n in valid_names][:max_skills]
        if not names:
            names = [fallback_name]
        for name in names:
            registry.read_skill(name)
        return json.dumps({
            "skill_names": names,
            "catalog_snapshot": catalog_snapshot,
            "reason": "tool_load",
        })

    return load_research_skills


def parse_load_skills_result(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return {}
