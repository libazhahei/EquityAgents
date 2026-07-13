"""Pydantic schemas for section research subgraph."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

StepAction = Literal[
    "orient",
    "search",
    "fetch_primary",
    "extract",
    "calculate",
    "compare",
    "verify",
    "synthesize",
]

StepStatus = Literal["pending", "in_progress", "done", "failed", "skipped"]
TaskStatus = Literal["pending", "in_progress", "done", "blocked"]
TodoStatus = Literal["pending", "in_progress", "done", "cancelled"]
TodoSource = Literal["planner", "executor", "reflector", "human"]
DataQuality = Literal["high", "medium", "low"]
NextAction = Literal["run_existing_queue", "plan_more", "needs_human", "exit"]

SECTION_RESEARCH_DIMENSIONS: tuple[str, ...] = (
    "question_coverage",
    "primary_source_evidence",
    "calculation_completeness",
    "citation_quality",
    "data_quality",
    "answer_card_confidence",
    "coverage_output_alignment",
    "contradiction_resolution",
)


class ResearchStep(BaseModel):
    step_id: str
    order: int = 1
    action: StepAction = "search"
    description: str = ""
    tool_hints: list[str] = Field(default_factory=list)
    inputs_from: list[str] = Field(default_factory=list)
    expected_output: str = ""
    status: StepStatus = "pending"
    result_summary: str | None = None


class ResearchTask(BaseModel):
    task_id: str
    question_id: str
    objective: str = ""
    task_type: str = "evidence_search"
    priority: int = 50
    steps: list[ResearchStep] = Field(default_factory=list)
    required_sources: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    success_criteria: dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = "pending"


class SectionResearchPlan(BaseModel):
    plan_id: str = ""
    section_id: str = ""
    version: int = 1
    tasks: list[ResearchTask] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    plan_rationale: str = ""
    plan_history: list[dict[str, Any]] = Field(default_factory=list)


class ResearchTodoItem(BaseModel):
    item_id: str
    title: str
    description: str = ""
    question_id: str | None = None
    task_id: str | None = None
    step_id: str | None = None
    action: str | None = None
    priority: int = 50
    status: TodoStatus = "pending"
    source: TodoSource = "planner"
    tool_hints: list[str] = Field(default_factory=list)
    blackboard_entry_id: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: str | None = None


class ResearchTodoList(BaseModel):
    list_id: str = ""
    section_id: str = ""
    version: int = 1
    items: list[ResearchTodoItem] = Field(default_factory=list)


class ResearchBrief(BaseModel):
    section_id: str
    section_title: str = ""
    planning_thesis: str = ""
    root_question: str = ""
    questions: list[dict[str, Any]] = Field(default_factory=list)
    coverage_outputs: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)
    planner_notes: str | None = None
    consensus_view: dict[str, Any] | str | None = None
    assumption_view: dict[str, Any] | None = None
    consensus_report: str = ""
    assumption_report: str = ""
    intent_hint: str = ""


class QuantifiedClaim(BaseModel):
    metric: str
    value_or_range: str
    unit: str = ""
    period: str = ""
    driver_link: str = ""
    confidence: float = 0.0


class SourceAttribution(BaseModel):
    source_type: str
    fiscal_quarter_or_date: str
    platform: str
    traceable_ref: str
    url: str = ""


class DataAvailabilityNote(BaseModel):
    metric: str
    status: Literal["available", "unavailable", "proxy_used"] = "available"
    attempted_sources: list[str] = Field(default_factory=list)
    rationale: str = ""
    proxy_metric: str = ""


class AnswerCard(BaseModel):
    question_id: str
    question: str = ""
    short_answer: str = ""
    verified_facts: list[dict[str, Any]] = Field(default_factory=list)
    inferred_estimates: list[dict[str, Any]] = Field(default_factory=list)
    quantified_claims: list[QuantifiedClaim] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    source_attributions: list[SourceAttribution] = Field(default_factory=list)
    named_competitive_threats: list[dict[str, Any]] = Field(default_factory=list)
    data_availability_notes: list[DataAvailabilityNote] = Field(default_factory=list)
    confidence: float = 0.0
    data_quality: DataQuality = "medium"
    open_gaps: list[str] = Field(default_factory=list)
    contradiction_flags: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)
    draft_paragraph: str | None = None


class PlanCompletion(BaseModel):
    tasks_total: int = 0
    tasks_done: int = 0
    steps_total: int = 0
    steps_done: int = 0
    blocked_steps: list[str] = Field(default_factory=list)


class SectionCoverageReport(BaseModel):
    overall_score: float = 0.0
    plan_completion: PlanCompletion = Field(default_factory=PlanCompletion)
    question_scores: dict[str, float] = Field(default_factory=dict)
    coverage_outputs_completed: list[str] = Field(default_factory=list)
    critical_gaps: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_issues: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_action: NextAction = "run_existing_queue"
    routing_decision: str = "continue"


class SectionCoverageEvaluation(BaseModel):
    overall_score: float = 0.0
    plan_completion: PlanCompletion = Field(default_factory=PlanCompletion)
    question_scores: dict[str, float] = Field(default_factory=dict)
    coverage_outputs_completed: list[str] = Field(default_factory=list)
    critical_gaps: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_issues: list[dict[str, Any]] = Field(default_factory=list)
    contradictions: list[dict[str, Any]] = Field(default_factory=list)
    recommended_next_action: NextAction = "run_existing_queue"
    completed_todo_ids: list[str] = Field(default_factory=list)


class SectionResearchView(BaseModel):
    ticker: str = ""
    section_id: str = ""
    section_title: str = ""
    as_of: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    coverage_score: float = 0.0
    answer_cards: dict[str, AnswerCard] = Field(default_factory=dict)
    section_draft: str = ""
    key_tables: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)
    model_inputs: dict[str, Any] = Field(default_factory=dict)
    dimension_coverage: dict[str, float] = Field(default_factory=dict)

    def to_legacy_summary(self) -> str:
        lines = [f"# {self.section_title or self.section_id}", ""]
        for qid, card in self.answer_cards.items():
            lines.append(f"## {qid}: {card.question[:80]}")
            lines.append(card.short_answer or "(pending)")
            lines.append("")
        if self.section_draft:
            lines.append(self.section_draft)
        return "\n".join(lines).strip()


class SectionResearchViewUpdate(BaseModel):
    ticker: str = ""
    section_id: str = ""
    answer_cards: dict[str, AnswerCard] = Field(default_factory=dict)
    section_draft: str = ""
    key_tables: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)
    model_inputs: dict[str, Any] = Field(default_factory=dict)


class SectionResearchOutput(BaseModel):
    section_id: str = ""
    section_title: str = ""
    final_section_text: str = ""
    executive_summary: str = ""
    answer_cards: dict[str, AnswerCard] = Field(default_factory=dict)
    key_tables: list[dict[str, Any]] = Field(default_factory=list)
    calculations: list[dict[str, Any]] = Field(default_factory=list)
    citations: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_notes: list[str] = Field(default_factory=list)
    unresolved_gaps: list[str] = Field(default_factory=list)
    model_inputs: dict[str, Any] = Field(default_factory=dict)
    research_plan: SectionResearchPlan | None = None
    research_todo_list: ResearchTodoList | None = None


class PlannerTaskOutline(BaseModel):
    task_id: str
    question_id: str
    objective: str = ""
    approach: str = ""


class SectionResearchPlanOutlineLLMOutput(BaseModel):
    plan_rationale: str = ""
    tasks: list[PlannerTaskOutline] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)


class SectionResearchPlanLLMOutput(BaseModel):
    plan_rationale: str = ""
    tasks: list[ResearchTask] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)


class SectionReplanLLMOutput(BaseModel):
    new_tasks: list[PlannerTaskOutline] = Field(default_factory=list)
    append_steps: list[dict[str, Any]] = Field(default_factory=list)
    new_todo_items: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str = ""


def empty_section_research_view(ticker: str, section_id: str = "", section_title: str = "") -> SectionResearchView:
    return SectionResearchView(ticker=ticker, section_id=section_id, section_title=section_title)


def empty_section_research_plan(section_id: str) -> SectionResearchPlan:
    return SectionResearchPlan(
        plan_id=f"plan_{section_id}",
        section_id=section_id,
    )


def empty_research_todo_list(section_id: str) -> ResearchTodoList:
    return ResearchTodoList(
        list_id=f"todo_{section_id}",
        section_id=section_id,
    )
