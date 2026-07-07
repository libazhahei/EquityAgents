"""Section research TaskProfile instance."""

from __future__ import annotations

from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tasks.section_research.merge import (
    apply_evidence_heuristic,
    default_coverage_report,
    evaluation_to_report,
    format_section_view,
    merge_section_view,
)
from tradingagents.equity_research.tasks.section_research.prompts import (
    build_executor_system_prompt,
    build_finalizer_prompt,
    build_initial_plan_prompt,
    build_reflector_prompt,
    build_replan_prompt,
    build_skill_prompt,
    build_synthesizer_prompt,
)
from tradingagents.equity_research.tasks.section_research.schemas import (
    SECTION_RESEARCH_DIMENSIONS,
    SectionCoverageEvaluation,
    SectionResearchView,
    SectionResearchViewUpdate,
    empty_section_research_view,
)
from tradingagents.equity_research.tools.tool_sets import TOOL_GROUP_IDS

EXECUTOR_LANGCHAIN_TOOL_NAMES: tuple[str, ...] = (
    "list_research_todos",
    "add_research_todo",
    "remove_research_todo",
    "update_research_todo_status",
    "get_next_research_todo",
    "web_search",
    "batch_light_grounding_search",
    "news_search",
    "filings_search",
    "filing_reader",
    "transcript_search",
    "financial_statement_fetch",
    "table_extractor",
    "document_chunker",
    "reference_parser",
    "calculator",
    "time_series_analyzer",
    "conflict_detector",
    "citation_checker",
    "claim_evidence_checker",
    "memory_retrieve",
    "search_evidence",
    "search_claims",
    "search_assumptions",
    "search_consensus",
    "search_conflicts",
    "search_memory_timeline",
    "search_research_context",
    "memory_write",
    "store_evidence",
)


def _noop_queries(ticker: str) -> list:
    return []


def _noop_normalize(queries: list, ticker: str, use_default: bool) -> list:
    return []


SECTION_RESEARCH_TASK_PROFILE = TaskProfile(
    task_id="section_research",
    objective="Autonomous deep research for one equity report section",
    dimensions=SECTION_RESEARCH_DIMENSIONS,
    output_schema=SectionResearchView,
    view_update_schema=SectionResearchViewUpdate,
    coverage_eval_schema=SectionCoverageEvaluation,
    default_queries_fn=_noop_queries,
    normalize_queries_fn=_noop_normalize,
    merge_view_fn=merge_section_view,
    format_view_fn=format_section_view,
    empty_view_fn=empty_section_research_view,
    skill_objective="section_research",
    agent_visibility_id="section_research_subgraph",
    coverage_threshold=0.75,
    max_iterations=10,
    max_initial_queries=0,
    max_loop_queries=0,
    enable_human_review=False,
    report_max_chars=8000,
    max_skills=3,
    build_initial_planner_prompt=build_initial_plan_prompt,
    build_loop_planner_prompt=build_replan_prompt,
    build_synthesizer_prompt=build_synthesizer_prompt,
    build_reflector_prompt=build_reflector_prompt,
    build_finalizer_prompt=build_finalizer_prompt,
    build_skill_prompt=build_skill_prompt,
    default_coverage_report_fn=default_coverage_report,
    apply_evidence_heuristic_fn=apply_evidence_heuristic,
    evaluation_to_report_fn=evaluation_to_report,
    extra_config={
        "executor_langchain_tool_names": list(EXECUTOR_LANGCHAIN_TOOL_NAMES),
        "executor_mode": "react",
        "executor_max_tool_calls_per_step": 6,
        "build_executor_system_prompt": build_executor_system_prompt,
        "tool_node_name_by_caller": {
            "executor": "executor_tools_retrieval",
        },
        "executor_tool_groups": list(TOOL_GROUP_IDS),
    },
)
