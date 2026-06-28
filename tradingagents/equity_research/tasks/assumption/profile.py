"""Assumption TaskProfile instance."""

from __future__ import annotations

from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tasks.assumption.merge import merge_assumption_view
from tradingagents.equity_research.tasks.assumption.prompts import (
    apply_evidence_heuristic,
    build_finalizer_prompt,
    build_initial_planner_prompt,
    build_loop_planner_prompt,
    build_reflector_prompt,
    build_skill_prompt,
    build_synthesizer_prompt,
    default_coverage_report,
    evaluation_to_report,
    format_assumption_view,
)
from tradingagents.equity_research.tasks.assumption.queries import default_queries, normalize_query_items
from tradingagents.equity_research.tasks.assumption.schemas import (
    ASSUMPTION_DIMENSIONS,
    AssumptionCoverageEvaluation,
    AssumptionView,
    AssumptionViewUpdate,
    empty_assumption_view,
)

ASSUMPTION_TASK_PROFILE = TaskProfile(
    task_id="assumption",
    objective="Probe key assumptions behind market consensus and derive research directions",
    dimensions=ASSUMPTION_DIMENSIONS,
    output_schema=AssumptionView,
    view_update_schema=AssumptionViewUpdate,
    coverage_eval_schema=AssumptionCoverageEvaluation,
    default_queries_fn=default_queries,
    normalize_queries_fn=normalize_query_items,
    merge_view_fn=merge_assumption_view,
    format_view_fn=format_assumption_view,
    empty_view_fn=empty_assumption_view,
    skill_objective="assumption",
    agent_visibility_id="assumption_subgraph",
    coverage_threshold=0.7,
    max_iterations=3,
    max_initial_queries=5,
    max_loop_queries=2,
    enable_human_review=False,
    report_max_chars=4000,
    max_skills=2,
    build_initial_planner_prompt=build_initial_planner_prompt,
    build_loop_planner_prompt=build_loop_planner_prompt,
    build_synthesizer_prompt=build_synthesizer_prompt,
    build_reflector_prompt=build_reflector_prompt,
    build_finalizer_prompt=build_finalizer_prompt,
    build_skill_prompt=build_skill_prompt,
    default_coverage_report_fn=default_coverage_report,
    apply_evidence_heuristic_fn=apply_evidence_heuristic,
    evaluation_to_report_fn=evaluation_to_report,
)
