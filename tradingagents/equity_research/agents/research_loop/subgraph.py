"""Section research subgraph wrapper for research_loop."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tasks.section_research.profile import SECTION_RESEARCH_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.schemas import (
    SectionResearchOutput,
    SectionResearchView,
)
from tradingagents.equity_research.tasks.section_research.seed import seed_section_research_state
from tradingagents.equity_research.templates.report_template import MVP1_SECTION_ORDER


def _pick_section_id(parent: dict[str, Any]) -> str:
    explicit = parent.get("active_section_id")
    if explicit:
        return str(explicit)
    completed = set((parent.get("section_research_outputs") or {}).keys())
    for section_id in MVP1_SECTION_ORDER:
        if section_id not in completed and section_id in (parent.get("section_plans") or {}):
            return section_id
    for section_id in MVP1_SECTION_ORDER:
        if section_id not in completed:
            return section_id
    return MVP1_SECTION_ORDER[0]


def _map_section_research_result(
    deps: EquityResearchDeps,
    parent: dict[str, Any],
    result: dict[str, Any],
    profile: TaskProfile,
    *,
    section_id: str,
) -> dict[str, Any]:
    view_raw = result.get("structured_view") or {}
    try:
        view = SectionResearchView.model_validate(view_raw)
    except Exception:
        view = SectionResearchView(ticker=str(parent.get("ticker", "")), section_id=section_id)

    coverage = result.get("coverage_report") or {}
    action = coverage.get("recommended_next_action", "exit")
    iterations = int(parent.get("research_iterations", 0)) + 1
    max_iterations = int(parent.get("max_research_iterations", profile.max_iterations))

    if action == "exit" or iterations >= max_iterations:
        research_status = "sufficient"
    elif action == "needs_human":
        research_status = "needs_human"
    else:
        research_status = "continue"

    output = SectionResearchOutput(
        section_id=section_id,
        section_title=view.section_title or section_id,
        final_section_text=result.get("final_report", ""),
        executive_summary=(result.get("final_report", "") or "")[:500],
        answer_cards=view.answer_cards,
        key_tables=view.key_tables,
        calculations=view.calculations,
        citations=view.citations,
        data_quality_notes=view.data_quality_notes,
        unresolved_gaps=view.unresolved_gaps,
        model_inputs=view.model_inputs,
    )
    if result.get("research_plan"):
        from tradingagents.equity_research.tasks.section_research.schemas import SectionResearchPlan
        output.research_plan = SectionResearchPlan.model_validate(result["research_plan"])
    if result.get("research_todo_list"):
        from tradingagents.equity_research.tasks.section_research.schemas import ResearchTodoList
        output.research_todo_list = ResearchTodoList.model_validate(result["research_todo_list"])

    section_outputs = dict(parent.get("section_research_outputs") or {})
    section_outputs[section_id] = output.model_dump()

    updates: dict[str, Any] = {
        "section_research_outputs": section_outputs,
        "answer_cards": result.get("answer_cards") or {},
        "research_plan": result.get("research_plan"),
        "research_todo_list": result.get("research_todo_list"),
        "research_iterations": iterations,
        "research_status": research_status,
        "active_section_id": section_id,
        "coverage_report": coverage,
        "final_report": result.get("final_report", ""),
        "documents": result.get("documents", parent.get("documents", [])),
        "api_calls": result.get("api_calls", parent.get("api_calls", 0)),
        "research_traces": result.get("research_traces", parent.get("research_traces", [])),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    if result.get("errors"):
        errors = list(parent.get("errors", []))
        errors.extend(result["errors"])
        updates["errors"] = errors
    updates.update(deps.trace({**parent, **updates}, "section_research_subgraph", {
        "section_id": section_id,
        "iterations": iterations,
        "status": research_status,
        "action": action,
    }))
    return updates


def create_run_section_research_subgraph(
    deps: EquityResearchDeps,
    *,
    profile: TaskProfile | None = None,
    checkpointer=None,
):
    tp = profile or SECTION_RESEARCH_TASK_PROFILE
    compiled = SectionResearchSubgraph(deps, tp).compile(checkpointer=checkpointer)

    def run_subgraph(state: dict[str, Any]) -> dict[str, Any]:
        section_id = _pick_section_id(state)
        section_plan = (state.get("section_plans") or {}).get(section_id, {})
        subgraph_input = seed_section_research_state(
            state, tp, section_id=section_id, section_plan=section_plan,
        )
        result = compiled.invoke(subgraph_input)
        return _map_section_research_result(
            deps, state, result, tp, section_id=section_id,
        )

    return run_subgraph
