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
from tradingagents.equity_research.tasks.section_research.memory_seed import merge_subgraph_ledgers_to_parent
from tradingagents.equity_research.tasks.section_research.seed import seed_section_research_state
from tradingagents.equity_research.memory.pruning import run_memory_maintenance
from tradingagents.equity_research.memory.snapshots import capture_iteration_snapshot
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


def _generate_blackboard_summary(
    deps: EquityResearchDeps,
    blackboard_entries: list[dict],
    section_id: str,
    ticker: str,
) -> str:
    """Generate a concise summary of blackboard entries using quick_llm.

    The summary captures key findings, contradictions, and methodology insights
    from the session for later sections to reference.
    """
    if not blackboard_entries:
        return ""

    # Format entries for the prompt
    entries_text = []
    for entry in blackboard_entries[:30]:  # Cap at 30 entries
        entry_type = entry.get("entry_type", "finding")
        content = entry.get("content", "")
        tags = entry.get("tags", [])
        tags_str = f" [{', '.join(tags[:3])}]" if tags else ""
        entries_text.append(f"- [{entry_type}]{tags_str} {content}")

    entries_block = "\n".join(entries_text)

    prompt = (
        f"Summarize the key research insights from the {section_id} section for ticker {ticker}.\n"
        f"Focus on: critical findings, contradictions discovered, methodology notes, "
        f"and cross-section hints.\n"
        f"Keep the summary under 500 characters.\n\n"
        f"Session blackboard entries:\n{entries_block}\n\n"
        f"Summary:"
    )

    try:
        response = deps.quick_llm.invoke(prompt)
        summary = response.content if hasattr(response, "content") else str(response)
        return summary[:600]  # Hard cap
    except Exception:
        # Fallback: simple concatenation of top entries
        top_entries = [e.get("content", "")[:100] for e in blackboard_entries[:5]]
        return "Key findings: " + "; ".join(top_entries)


def _persist_blackboard_to_store(
    deps: EquityResearchDeps,
    report_id: str,
    section_id: str,
    blackboard_entries: list[dict],
    ticker: str,
) -> str:
    """Save blackboard to store and generate summary. Returns summary string."""
    if not blackboard_entries:
        return ""

    # Save full entries to store
    store = getattr(deps, "blackboard_store", None)
    if store is not None:
        try:
            store.save_session_blackboard(report_id, section_id, blackboard_entries, ticker=ticker)
        except Exception:
            pass

    # Generate summary
    summary = _generate_blackboard_summary(deps, blackboard_entries, section_id, ticker)

    # Save summary to store
    if store is not None and summary:
        try:
            store.save_session_summary(report_id, section_id, summary)
        except Exception:
            pass

    return summary


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
    updates.update(merge_subgraph_ledgers_to_parent(parent, result))

    # Persist blackboard and generate summary for cross-section reference
    blackboard_entries = result.get("blackboard") or []
    if blackboard_entries:
        report_id = str(parent.get("report_id", ""))
        ticker = str(parent.get("ticker", ""))
        summary = _persist_blackboard_to_store(deps, report_id, section_id, blackboard_entries, ticker)
        if summary:
            # Add to parent's session_blackboard_summaries
            existing_summaries = list(parent.get("session_blackboard_summaries") or [])
            # Remove any existing summary for this section
            existing_summaries = [s for s in existing_summaries if s.get("section_id") != section_id]
            existing_summaries.append({"section_id": section_id, "summary": summary})
            updates["session_blackboard_summaries"] = existing_summaries

    merged = {**parent, **updates}
    updates.update(run_memory_maintenance(merged, deps))
    updates.update(capture_iteration_snapshot({**merged, **updates}, deps))
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
        er = deps.config.get("equity_research", {})
        recursion_limit = int(
            er.get("section_research_recursion_limit", er.get("max_recur_limit", 200))
        )
        section_id = _pick_section_id(state)
        section_plan = (state.get("section_plans") or {}).get(section_id, {})
        state = {**state, "_section_research_recursion_limit": recursion_limit}
        subgraph_input = seed_section_research_state(
            state, tp, section_id=section_id, section_plan=section_plan,
        )
        result = compiled.invoke(
            subgraph_input,
            config={"recursion_limit": recursion_limit},
        )
        return _map_section_research_result(
            deps, state, result, tp, section_id=section_id,
        )

    return run_subgraph
