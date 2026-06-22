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


class SkillManifest(BaseModel):
    name: str
    description: str = ""
    trigger: list[str] = Field(default_factory=list)
    required_inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    quality_gates: list[str] = Field(default_factory=list)


class Skill(Protocol):
    name: str
    manifest: SkillManifest

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput: ...
