"""Skill protocol and base types for equity research."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field


class SkillInput(BaseModel):
    mandate: dict = Field(default_factory=dict)
    state_snapshot: dict = Field(default_factory=dict)
    objective: str = ""
    constraints: dict | None = None


class SkillOutput(BaseModel):
    summary: str = ""
    claims: list[dict] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    assumptions: list[dict] = Field(default_factory=list)
    confidence: float = 0.0
    data_quality_flags: list[str] = Field(default_factory=list)
    next_questions: list[str] = Field(default_factory=list)
    artifacts: dict[str, Any] = Field(default_factory=dict)


class SkillCatalogEntry(BaseModel):
    """Lightweight skill index from frontmatter only (injected into LLM catalog)."""

    name: str
    description: str
    when_to_use: str
    tags: list[str] = Field(default_factory=list)
    source_path: str = ""
    tools: list[str] = Field(default_factory=list)
    handler: str | None = None
    compatible_with: list[str] = Field(default_factory=list)
    composable: bool = False
    version: int = 1

    def to_prompt_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "when_to_use": self.when_to_use,
            "tags": self.tags,
        }
    
    def to_prompt(self) -> str:
        return (
            f"Name: {self.name}\n"
            f"- Description: {self.description}\n"
            f"- When to use: {self.when_to_use}\n"
            f"- Tags: {self.tags}\n\n"
        )


class ManifestSummary(BaseModel):
    name: str
    description: str
    when_to_use: str
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_catalog_entry(cls, entry: SkillCatalogEntry) -> ManifestSummary:
        return cls(
            name=entry.name,
            description=entry.description,
            when_to_use=entry.when_to_use,
            tags=entry.tags,
        )


class LoadedSkill(BaseModel):
    manifest: ManifestSummary
    constraints: str
    prompt_template: str
    query_guidance: str = ""
    tools: list[str] = Field(default_factory=list)
    compatible_with: list[str] = Field(default_factory=list)
    composable: bool = False
    handler: str | None = None
    output_schema: dict[str, Any] = Field(default_factory=dict)
    source_path: str = ""
    version: int = 1

    @property
    def allowed_tools(self) -> list[str]:
        return self.tools

    @property
    def name(self) -> str:
        return self.manifest.name


class SkillManifest(BaseModel):
    """Legacy manifest shape for backward-compatible callers."""

    name: str
    description: str = ""
    when_to_use: str = ""
    trigger: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    quality_gates: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @classmethod
    def from_loaded(cls, loaded: LoadedSkill) -> SkillManifest:
        return cls(
            name=loaded.manifest.name,
            description=loaded.manifest.description,
            when_to_use=loaded.manifest.when_to_use,
            allowed_tools=loaded.tools,
            tags=loaded.manifest.tags,
            quality_gates=_constraints_to_gates(loaded.constraints),
        )


def _constraints_to_gates(constraints: str) -> list[str]:
    gates = []
    for line in constraints.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped:
            gates.append(stripped)
    return gates[:5]


class SkillHandler(Protocol):
    def run(
        self,
        loaded: LoadedSkill,
        input: SkillInput,
        tools: dict[str, Any],
    ) -> SkillOutput: ...


class Skill(Protocol):
    name: str
    manifest: SkillManifest

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput: ...
