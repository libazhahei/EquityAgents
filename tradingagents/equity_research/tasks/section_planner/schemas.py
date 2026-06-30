"""Pydantic schemas for section question tree planner."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SectionPlannerRequest(BaseModel):
    ticker: str
    section_id: str
    section_title: str
    required_outputs: list[str]
    background_reports: dict[str, str] = Field(default_factory=dict)
    user_focus: str | None = None
    time_horizon: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    extra_context: dict[str, Any] = Field(default_factory=dict)
    enable_grounding: bool = False
    section_intent_hint: str = ""


class ResearchQuestionNode(BaseModel):
    id: str
    parent_id: str | None = None
    level: int = 0
    question: str = ""
    rationale: str = ""
    priority: int = 1
    required_evidence: list[str] = Field(default_factory=list)
    suggested_sources: list[str] = Field(default_factory=list)
    expected_output: str = ""
    downstream_agent: str | None = None
    stop_condition_hint: str | None = None


class SectionResearchPlan(BaseModel):
    ticker: str
    section_id: str
    section_title: str
    planning_thesis: str = ""
    root_question: str = ""
    nodes: list[ResearchQuestionNode] = Field(default_factory=list)
    coverage_map: dict[str, list[str]] = Field(default_factory=dict)
    execution_order: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)
    planner_notes: str | None = None


class BackgroundExtraction(BaseModel):
    market_implied_assumptions: list[str] = Field(default_factory=list)
    controversies: list[str] = Field(default_factory=list)
    model_drivers: list[str] = Field(default_factory=list)
    evidence_for: list[str] = Field(default_factory=list)
    evidence_against: list[str] = Field(default_factory=list)
    falsification_tests: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    next_data_to_watch: list[str] = Field(default_factory=list)


class SectionPlannerLLMOutput(BaseModel):
    planning_thesis: str = ""
    root_question: str = ""
    nodes: list[ResearchQuestionNode] = Field(default_factory=list)
    coverage_map: dict[str, list[str]] = Field(default_factory=dict)
    execution_order: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)
    planner_notes: str | None = None
