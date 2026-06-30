"""Per-agent skill visibility configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tradingagents.equity_research.skills.base import SkillCatalogEntry


@dataclass
class AgentSkillVisibility:
    agent_id: str
    include_names: list[str] = field(default_factory=list)
    include_tags_any: list[str] = field(default_factory=list)
    exclude_names: list[str] = field(default_factory=list)
    exclude_tags_any: list[str] = field(default_factory=list)


AGENT_SKILL_VISIBILITY: dict[str, AgentSkillVisibility] = {
    "consensus_subgraph": AgentSkillVisibility(
        agent_id="consensus_subgraph",
        include_names=["broker_consensus_mining", "variant_view_discovery"],
        exclude_names=["market_assumption_decomposition"],
    ),
    "assumption_subgraph": AgentSkillVisibility(
        agent_id="assumption_subgraph",
        include_names=["market_assumption_decomposition", "variant_view_discovery"],
        exclude_names=["broker_consensus_mining"],
    ),
    "research_loop": AgentSkillVisibility(
        agent_id="research_loop",
        exclude_tags_any=["writing", "qa"],
    ),
    "dynamic_planning": AgentSkillVisibility(
        agent_id="dynamic_planning",
        include_tags_any=["planning", "thesis", "reasoning", "memory"],
    ),
    "risk_mapping": AgentSkillVisibility(
        agent_id="risk_mapping",
        include_names=["risk_counterthesis"],
    ),
    "section_writing": AgentSkillVisibility(
        agent_id="section_writing",
        include_names=["section_writing"],
    ),
}


def resolve_agent_visibility(
    agent_id: str,
    config: dict[str, Any] | None = None,
) -> AgentSkillVisibility:
    base = AGENT_SKILL_VISIBILITY.get(agent_id, AgentSkillVisibility(agent_id=agent_id))
    if not config:
        return base
    overrides = (config.get("equity_research") or {}).get("agent_skills", {}).get(agent_id)
    if not overrides:
        return base
    return AgentSkillVisibility(
        agent_id=agent_id,
        include_names=list(overrides.get("include_names", base.include_names)),
        include_tags_any=list(overrides.get("include_tags_any", base.include_tags_any)),
        exclude_names=list(overrides.get("exclude_names", base.exclude_names)),
        exclude_tags_any=list(overrides.get("exclude_tags_any", base.exclude_tags_any)),
    )


def _tags_match(entry: SkillCatalogEntry, tags: list[str]) -> bool:
    if not tags:
        return False
    entry_tags = {t.lower() for t in entry.tags}
    return any(t.lower() in entry_tags for t in tags)


def filter_eligible_catalog(
    catalog: list[SkillCatalogEntry],
    visibility: AgentSkillVisibility,
) -> list[SkillCatalogEntry]:
    by_name = {entry.name: entry for entry in catalog}
    selected: list[SkillCatalogEntry] = []

    if visibility.include_names:
        for name in visibility.include_names:
            if name in by_name:
                selected.append(by_name[name])
        for entry in catalog:
            if _tags_match(entry, visibility.include_tags_any) and entry not in selected:
                selected.append(entry)
    elif visibility.include_tags_any:
        selected = [e for e in catalog if _tags_match(e, visibility.include_tags_any)]
    else:
        selected = list(catalog)

    exclude_names = set(visibility.exclude_names)
    exclude_tags = visibility.exclude_tags_any
    filtered: list[SkillCatalogEntry] = []
    for entry in selected:
        if entry.name in exclude_names:
            continue
        if exclude_tags and _tags_match(entry, exclude_tags):
            continue
        filtered.append(entry)
    return filtered
