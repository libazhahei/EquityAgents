"""Skill catalog formatting and filtering helpers."""

from __future__ import annotations

import json

from tradingagents.equity_research.skills.agent_visibility import (
    AgentSkillVisibility,
    filter_eligible_catalog,
    resolve_agent_visibility,
)
from tradingagents.equity_research.skills.base import SkillCatalogEntry

__all__ = [
    "AgentSkillVisibility",
    "filter_eligible_catalog",
    "format_catalog_for_prompt",
    "resolve_agent_visibility",
]


def format_catalog_for_prompt(entries: list[SkillCatalogEntry]) -> str:
    """Serialize catalog entries for LLM prompt (name, description, when_to_use, tags only)."""
    payload = "\n".join([f"|{entry.name}|{entry.description}|{entry.when_to_use}|{entry.tags}|" for entry in entries])
    return (
        "|Name|Description|When to use|Tags|\n"
        "|----|-----------|-----------|----|\n"
        f"{payload}\n"
    )
