"""Task profile — parameterizes generic research subgraph behavior."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel


@dataclass
class TaskProfile:
    task_id: str
    objective: str
    dimensions: tuple[str, ...]
    output_schema: type[BaseModel]
    view_update_schema: type[BaseModel]
    coverage_eval_schema: type[BaseModel]
    default_queries_fn: Callable[[str], list]
    normalize_queries_fn: Callable[[list, str, bool], list]
    merge_view_fn: Callable[[Any, Any], Any]
    format_view_fn: Callable[[Any], str]
    empty_view_fn: Callable[[str], BaseModel]
    skill_objective: str
    agent_visibility_id: str = ""
    coverage_threshold: float = 0.75
    max_iterations: int = 5
    max_initial_queries: int = 5
    max_loop_queries: int = 2
    enable_assumption_probe: bool = False
    enable_human_review: bool = False
    report_max_chars: int = 6000
    assumption_schema: type[BaseModel] | None = None
    max_skills: int = 2
    build_initial_planner_prompt: Callable[[Any, Any], str] | None = None
    build_loop_planner_prompt: Callable[[Any, Any], str] | None = None
    build_synthesizer_prompt: Callable[[Any, Any, Any, list], str] | None = None
    build_reflector_prompt: Callable[[Any, Any, str], str] | None = None
    build_finalizer_prompt: Callable[[Any, dict], str] | None = None
    build_assumption_planner_prompt: Callable[[Any, Any], str] | None = None
    build_assumption_synth_prompt: Callable[[Any, Any, str], str] | None = None
    build_skill_prompt: Callable[[dict, str, str], str] | None = None
    normalize_assumption_queries_fn: Callable[[list, str, bool], list] | None = None
    default_coverage_report_fn: Callable[[Any], Any] | None = None
    apply_evidence_heuristic_fn: Callable[[Any, list], None] | None = None
    preserve_citations_fn: Callable[[Any, list], None] | None = None
    evaluation_to_report_fn: Callable[[Any], Any] | None = None
    extra_config: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.agent_visibility_id:
            self.agent_visibility_id = f"{self.task_id}_subgraph"

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "objective": self.objective,
            "dimensions": list(self.dimensions),
            "coverage_threshold": self.coverage_threshold,
            "max_iterations": self.max_iterations,
            "enable_assumption_probe": self.enable_assumption_probe,
            "enable_human_review": self.enable_human_review,
            "agent_visibility_id": self.agent_visibility_id,
        }
