"""Seed research brief and agent state for section research subgraph."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.runtime.state import AgentState, empty_agent_state
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchBrief,
    empty_research_todo_list,
    empty_section_research_plan,
    empty_section_research_view,
)
from tradingagents.equity_research.tasks.section_research.bfs_todos import bfs_levels
from tradingagents.equity_research.templates.report_template import MVP1_REPORT_TEMPLATE


def build_research_brief(
    *,
    ticker: str,
    section_id: str,
    section_plan: dict[str, Any],
    consensus_view: dict[str, Any] | None = None,
    assumption_view: dict[str, Any] | None = None,
    assumption_report: str = "",
) -> ResearchBrief:
    template = MVP1_REPORT_TEMPLATE.get(section_id, {})
    nodes = section_plan.get("nodes", [])
    return ResearchBrief(
        section_id=section_id,
        section_title=str(section_plan.get("section_title") or template.get("title", section_id)),
        planning_thesis=str(section_plan.get("planning_thesis", "")),
        root_question=str(section_plan.get("root_question", "")),
        questions=[dict(n) for n in nodes],
        coverage_outputs=list(template.get("required_outputs", [])),
        data_quality_flags=list(section_plan.get("data_quality_flags", [])),
        planner_notes=section_plan.get("planner_notes"),
        consensus_view=consensus_view,
        assumption_view=assumption_view,
        assumption_report=assumption_report,
        intent_hint=str(template.get("intent_hint", "")),
    )


def build_question_graph(section_plan: dict[str, Any]) -> dict[str, Any]:
    nodes = section_plan.get("nodes", [])
    return {
        "root_question": section_plan.get("root_question", ""),
        "nodes": {str(n.get("id", "")): dict(n) for n in nodes if n.get("id")},
        "coverage_map": dict(section_plan.get("coverage_map", {})),
        "execution_order": list(section_plan.get("execution_order", [])),
    }


def seed_section_research_state(
    parent: dict[str, Any],
    profile: TaskProfile,
    *,
    section_id: str,
    section_plan: dict[str, Any] | None = None,
) -> AgentState:
    plan_data = section_plan or (parent.get("section_plans") or {}).get(section_id, {})
    brief = build_research_brief(
        ticker=str(parent.get("ticker", "")),
        section_id=section_id,
        section_plan=plan_data,
        consensus_view=parent.get("consensus_view"),
        assumption_view=parent.get("assumption_view"),
        assumption_report=str(parent.get("assumption_report", "")),
    )
    max_iter = int(parent.get("max_section_research_iterations", profile.max_iterations))
    subgraph_input = empty_agent_state(
        parent,
        task_profile=profile.to_dict(),
        max_iterations=max_iter,
    )
    ticker = str(parent.get("ticker", ""))
    subgraph_input["section_id"] = section_id
    subgraph_input["research_brief"] = brief.model_dump()
    question_graph = build_question_graph(plan_data)
    subgraph_input["question_graph"] = question_graph
    subgraph_input["bfs_levels"] = bfs_levels(question_graph)
    subgraph_input["bfs_wave_index"] = 0
    subgraph_input["research_plan"] = empty_section_research_plan(section_id).model_dump()
    subgraph_input["research_todo_list"] = empty_research_todo_list(section_id).model_dump()
    subgraph_input["structured_view"] = empty_section_research_view(
        ticker, section_id, brief.section_title,
    ).model_dump()
    subgraph_input["answer_cards"] = {}
    subgraph_input["fact_store"] = []
    subgraph_input["calculation_store"] = []
    subgraph_input["task_queue"] = []
    subgraph_input["active_task"] = None
    subgraph_input["active_step"] = None
    subgraph_input["plan_history"] = []
    subgraph_input["unresolved_gaps"] = []
    subgraph_input["section_draft"] = ""
    subgraph_input["status"] = "continue"
    subgraph_input["parent_context"] = {
        **dict(parent.get("parent_context", {})),
        "consensus_view": parent.get("consensus_view", {}),
        "assumption_view": parent.get("assumption_view", {}),
        "consensus_report": parent.get("consensus_report", ""),
        "assumption_report": parent.get("assumption_report", ""),
        "section_plan": plan_data,
    }
    subgraph_input["research_objective"] = (
        f"Section research: {brief.section_title} — {brief.root_question[:200]}"
    )
    subgraph_input["report_id"] = parent.get("report_id") or f"sr_{uuid.uuid4().hex[:8]}"
    return subgraph_input
