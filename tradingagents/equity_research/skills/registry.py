"""Skill registry — file-based definitions with lazy catalog loading."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from tradingagents.equity_research.skills.agent_visibility import (
    filter_eligible_catalog,
    resolve_agent_visibility,
)
from tradingagents.equity_research.skills.base import LoadedSkill, ManifestSummary, SkillCatalogEntry
from tradingagents.equity_research.skills.loader import DEFAULT_DEFINITIONS_DIR, SkillLoader
from tradingagents.equity_research.skills.runnable import RunnableSkill


OBJECTIVE_SKILL_MAP = {
    "consensus": "broker_consensus_mining",
    "assumption": "market_assumption_decomposition",
    "variant_view": "variant_view_discovery",
    "section_research": "section_3_business_model",
    "default": "variant_view_discovery",
}

_SECTION_SKILL_PREFIX = "section_"


def section_skill_for_id(section_id: str) -> str:
    normalized = section_id.strip().lower().replace("-", "_")
    return f"{_SECTION_SKILL_PREFIX}{normalized}"


def section_skill_objective(section_id: str) -> str:
    return section_skill_for_id(section_id)


class SkillRegistry:
    def __init__(
        self,
        definitions_dir: Path | str | None = None,
        *,
        deps: Any | None = None,
        known_tools: set[str] | None = None,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.deps = deps
        self.config = config or (getattr(deps, "config", None) if deps else None) or {}
        self._definitions_dir = Path(definitions_dir) if definitions_dir else _resolve_definitions_dir()
        self._loader = SkillLoader(definitions_dir=self._definitions_dir, known_tools=known_tools)
        self._catalog: dict[str, SkillCatalogEntry] = {}
        self._loaded: dict[str, LoadedSkill] = {}
        self._runnable: dict[str, RunnableSkill] = {}
        self._scan()

    @property
    def load_errors(self) -> list[str]:
        return self._loader.load_errors

    @property
    def load_warnings(self) -> list[str]:
        return self._loader.load_warnings

    def reload(self) -> None:
        self._loader.reload()
        self._catalog.clear()
        self._loaded.clear()
        self._runnable.clear()
        self._scan()

    def _scan(self) -> None:
        self._catalog = self._loader.scan_catalog()

    def _llm(self) -> Any | None:
        if self.deps is None:
            return None
        return getattr(self.deps, "quick_llm", None) or getattr(self.deps, "deep_llm", None)

    def get_catalog(self) -> list[SkillCatalogEntry]:
        return list(self._catalog.values())

    def get_eligible_catalog(self, agent_id: str) -> list[SkillCatalogEntry]:
        visibility = resolve_agent_visibility(agent_id, self.config)
        return filter_eligible_catalog(self.get_catalog(), visibility)

    def get_manifests_summary(self) -> list[ManifestSummary]:
        return [ManifestSummary.from_catalog_entry(entry) for entry in self._catalog.values()]

    def read_skill(self, name: str) -> LoadedSkill:
        if name in self._loaded:
            return self._loaded[name]
        entry = self._catalog.get(name)
        if entry is None:
            raise KeyError(f"Skill '{name}' not registered")
        loaded = self._loader.catalog_entry_to_loaded_skill(entry)
        self._loaded[name] = loaded
        return loaded

    def load(self, name: str) -> LoadedSkill:
        return self.read_skill(name)

    def get(self, name: str) -> RunnableSkill:
        if name not in self._runnable:
            loaded = self.read_skill(name)
            self._runnable[name] = RunnableSkill.from_loaded(loaded, llm=self._llm())
        return self._runnable[name]

    def register(self, skill: RunnableSkill) -> None:
        self._runnable[skill.name] = skill
        self._loaded[skill.name] = skill.loaded

    def list(self) -> list[str]:
        return list(self._catalog.keys())

    def select_for_objective(self, objective: str) -> str:
        objective_lower = objective.lower()
        if objective_lower.startswith(_SECTION_SKILL_PREFIX):
            if objective_lower in self._catalog:
                return objective_lower
        for key, skill_name in OBJECTIVE_SKILL_MAP.items():
            if key in objective_lower and skill_name in self._catalog:
                return skill_name
        default = OBJECTIVE_SKILL_MAP["default"]
        if default in self._catalog:
            return default
        return self.list()[0] if self.list() else default

    def manifests(self) -> list[dict]:
        return [self._summary_to_legacy_dict(m) for m in self.get_manifests_summary()]

    def _summary_to_legacy_dict(self, summary: ManifestSummary) -> dict:
        entry = self._catalog.get(summary.name)
        return {
            "name": summary.name,
            "description": summary.description,
            "when_to_use": summary.when_to_use,
            "tags": summary.tags,
            "allowed_tools": entry.tools if entry else [],
            "trigger": summary.tags,
        }


def _resolve_definitions_dir() -> Path:
    override = os.environ.get("EQUITY_RESEARCH_SKILLS_DIR")
    if override:
        return Path(override)
    return DEFAULT_DEFINITIONS_DIR
