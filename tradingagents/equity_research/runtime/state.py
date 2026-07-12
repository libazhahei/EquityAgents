"""Generic agent state for research subgraphs."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages

from tradingagents.equity_research.runtime.reducers import (
    calculation_store_reducer,
    documents_reducer,
    errors_reducer,
    evidence_buffer_reducer,
    fact_store_reducer,
    pending_evidence_reducer,
)
from tradingagents.equity_research.state.blackboard import blackboard_reducer


class AgentState(TypedDict, total=False):
    ticker: str
    sector: str
    report_type: str
    instrument_context: str
    report_id: str
    research_objective: str
    documents: Annotated[list[dict], documents_reducer]
    api_calls: int

    task_profile: dict[str, Any]
    parent_context: dict[str, Any]

    exploration_graph: dict[str, Any]
    current_node_id: str

    messages: Annotated[list[Any], add_messages]
    active_skills: list[str]
    active_skill_context: dict[str, Any]
    skill_catalog: list[dict]
    loaded_skills: list[str]

    query_queue: list[dict]
    executed_queries: list[str]
    evidence_buffer: Annotated[list[dict], evidence_buffer_reducer]
    pending_evidence: Annotated[list[dict], pending_evidence_reducer]
    search_memory: Annotated[list[dict], lambda e, n: e + n]

    structured_view: dict
    assumptions: dict
    final_report: str
    coverage_report: dict
    coverage_history: list[dict]
    iterations: int
    max_iterations: int

    assumption_probe_completed: bool
    assumption_pending_evidence: list[dict]

    human_followup_query: str
    human_followup_history: list[str]
    human_review_payload: dict[str, Any]
    _pending_human_followup: bool

    compliance_flags: list[dict]
    errors: Annotated[list[str], errors_reducer]
    research_traces: list[dict]
    last_updated: str

    _executor_batch: dict[str, Any] | None
    _executor_tool_node: str | None
    _executor_tool_group: str | None

    # Section research fields
    section_id: str
    research_brief: dict[str, Any]
    research_plan: dict[str, Any]
    research_todo_list: dict[str, Any]
    question_graph: dict[str, Any]
    task_queue: list[dict]
    active_task: dict[str, Any] | None
    active_step: dict[str, Any] | None
    plan_history: list[dict]
    answer_cards: dict[str, dict]
    fact_store: Annotated[list[dict], fact_store_reducer]
    calculation_store: Annotated[list[dict], calculation_store_reducer]
    section_draft: str
    unresolved_gaps: list[dict]
    status: str
    _executor_step_calls: int
    bfs_wave_index: int
    bfs_levels: list[list[str]]
    executor_context_snapshot: str
    question_iterations: dict[str, int]  # per-question reflector cycle counts

    # Parameter registry (ParameterPreservingReducer)
    parameter_registry: dict[str, Any]
    parameter_grid: str

    # Shared ledger fields (blackboard)
    consensus_ledger: list[dict]
    assumption_ledger: list[dict]
    evidence_ledger: list[dict]
    claim_ledger: list[dict]
    memory_reflections: list[dict]

    # Session blackboard — shared notes within a single section research session
    blackboard: Annotated[list[dict], blackboard_reducer]


def empty_agent_state(
    parent: dict[str, Any],
    *,
    task_profile: dict[str, Any] | None = None,
    max_iterations: int = 5,
) -> AgentState:
    search_memory_key = "consensus_search_memory"
    if task_profile and task_profile.get("task_id") != "consensus":
        search_memory_key = f"{task_profile['task_id']}_search_memory"

    return {
        "ticker": parent.get("ticker", ""),
        "sector": parent.get("sector", ""),
        "report_type": parent.get("report_type", "initiation"),
        "instrument_context": parent.get("instrument_context", ""),
        "report_id": parent.get("report_id", ""),
        "research_objective": parent.get("research_objective", ""),
        "documents": list(parent.get("documents", [])),
        "api_calls": int(parent.get("api_calls", 0)),
        "task_profile": task_profile or {},
        "parent_context": dict(parent.get("parent_context", {})),
        "exploration_graph": {},
        "current_node_id": "",
        "messages": [],
        "active_skills": [],
        "active_skill_context": {},
        "skill_catalog": [],
        "query_queue": [],
        "executed_queries": [],
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": list(parent.get(search_memory_key, parent.get("search_memory", []))),
        "structured_view": {},
        "assumptions": {},
        "final_report": "",
        "coverage_report": {},
        "coverage_history": [],
        "iterations": 0,
        "max_iterations": max_iterations,
        "assumption_probe_completed": False,
        "assumption_pending_evidence": [],
        "human_followup_query": "",
        "human_followup_history": list(parent.get("human_followup_history", [])),
        "human_review_payload": {},
        "compliance_flags": list(parent.get("compliance_flags", [])),
        "errors": list(parent.get("errors", [])),
        "research_traces": list(parent.get("research_traces", [])),
        # Parameter registry — initialised empty
        "parameter_registry": {"parameters": {}, "dimensions": []},
        "parameter_grid": "",
        # Session blackboard — initialised empty
        "blackboard": [],
        "question_iterations": {},
    }
