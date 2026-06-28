"""Consensus TaskProfile instance."""

from __future__ import annotations

from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    ConsensusAssumptions,
    ConsensusViewUpdate,
    CoverageEvaluation,
    StructuredConsensusView,
    empty_structured_consensus_view,
)
from tradingagents.equity_research.tasks.consensus.merge import (
    merge_view_update,
    preserve_citations_from_evidence,
    preserve_citations_from_memory,
)
from tradingagents.equity_research.tasks.consensus.prompts import (
    apply_evidence_heuristic,
    build_assumption_planner_prompt,
    build_assumption_synth_prompt,
    build_finalizer_prompt,
    build_initial_planner_prompt,
    build_loop_planner_prompt,
    build_reflector_prompt,
    build_skill_prompt,
    build_synthesizer_prompt,
    default_coverage_report,
    evaluation_to_report,
    format_consensus_view,
    normalize_assumption_queries,
)
from tradingagents.equity_research.tasks.consensus.queries import (
    default_queries,
    normalize_query_items,
)


def _preserve_citations(view, evidence):
    preserve_citations_from_evidence(view, evidence)


CONSENSUS_TASK_PROFILE = TaskProfile(
    task_id="consensus",
    objective="Build market consensus view across analyst estimates",
    dimensions=CONSENSUS_DIMENSIONS,
    output_schema=StructuredConsensusView,
    view_update_schema=ConsensusViewUpdate,
    coverage_eval_schema=CoverageEvaluation,
    assumption_schema=ConsensusAssumptions,
    default_queries_fn=default_queries,
    normalize_queries_fn=normalize_query_items,
    normalize_assumption_queries_fn=normalize_assumption_queries,
    merge_view_fn=merge_view_update,
    format_view_fn=format_consensus_view,
    empty_view_fn=empty_structured_consensus_view,
    skill_objective="consensus",
    agent_visibility_id="consensus_subgraph",
    coverage_threshold=0.75,
    max_iterations=5,
    max_initial_queries=5,
    max_loop_queries=2,
    enable_assumption_probe=False,
    enable_human_review=True,
    report_max_chars=6000,
    max_skills=2,
    build_initial_planner_prompt=build_initial_planner_prompt,
    build_loop_planner_prompt=build_loop_planner_prompt,
    build_synthesizer_prompt=build_synthesizer_prompt,
    build_reflector_prompt=build_reflector_prompt,
    build_finalizer_prompt=build_finalizer_prompt,
    build_assumption_planner_prompt=build_assumption_planner_prompt,
    build_assumption_synth_prompt=build_assumption_synth_prompt,
    build_skill_prompt=build_skill_prompt,
    default_coverage_report_fn=default_coverage_report,
    apply_evidence_heuristic_fn=apply_evidence_heuristic,
    preserve_citations_fn=_preserve_citations,
    evaluation_to_report_fn=evaluation_to_report,
    extra_config={"preserve_memory_citations_fn": preserve_citations_from_memory},
)
