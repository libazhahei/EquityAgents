"""Section research reflector — plan-aware coverage evaluation."""

from __future__ import annotations

from typing import Any
from datetime import datetime

from langchain_core.messages import HumanMessage, SystemMessage

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.executor_context import format_executor_messages
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.runtime.utils.search_memory import build_search_memory_for_prompt
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.tasks.section_research.bfs_todos import (
    has_next_bfs_wave,
    wave_complete,
)
from tradingagents.equity_research.tasks.section_research.merge import compute_plan_completion
from tradingagents.equity_research.tasks.section_research.prompts import (
    build_reflector_system_prompt,
    build_reflector_user_prompt,
)
from tradingagents.equity_research.tasks.section_research.schemas import SectionCoverageEvaluation
from tradingagents.equity_research.tasks.section_research.todo_sync import has_pending_tasks_or_steps
from tradingagents.equity_research.tasks.section_research.schemas import ResearchTodoList


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


# ---------------------------------------------------------------------------
# Per-question iteration helpers
# ---------------------------------------------------------------------------

def _get_question_iterations(state: dict[str, Any]) -> dict[str, int]:
    """Return the current per-question iteration counters."""
    return dict(state.get("question_iterations") or {})


def _active_question_ids(state: dict[str, Any]) -> set[str]:
    """Return question IDs that have pending work (tasks, steps, or todos)."""
    qids: set[str] = set()
    # From research_plan
    plan_raw = state.get("research_plan") or {}
    if plan_raw:
        from tradingagents.equity_research.tasks.section_research.schemas import SectionResearchPlan
        plan = SectionResearchPlan.model_validate(plan_raw)
        for task in plan.tasks:
            if task.status in ("pending", "in_progress"):
                qids.add(task.question_id)
            for step in task.steps:
                if step.status in ("pending", "in_progress"):
                    qids.add(task.question_id)
    # From todo list
    todo_raw = state.get("research_todo_list") or {}
    if todo_raw:
        todo = ResearchTodoList.model_validate(todo_raw)
        for item in todo.items:
            if item.status in ("pending", "in_progress") and item.question_id:
                qids.add(item.question_id)
    return qids


def _question_has_budget(state: dict[str, Any], question_id: str) -> bool:
    """True when a specific question still has iteration budget remaining."""
    max_iter = int(state.get("max_iterations", 5))
    q_iters = _get_question_iterations(state)
    return q_iters.get(question_id, 0) < max_iter


def _any_active_question_has_budget(state: dict[str, Any]) -> bool:
    """True when at least one active question still has iteration budget."""
    active_qids = _active_question_ids(state)
    if not active_qids:
        return False
    return any(_question_has_budget(state, qid) for qid in active_qids)


def _questions_exhausted(state: dict[str, Any]) -> bool:
    """True when ALL active questions have exhausted their per-question budget."""
    active_qids = _active_question_ids(state)
    if not active_qids:
        # No pending work — not exhausted, just no active questions
        # Let the LLM recommendation or other logic decide
        return False
    return all(not _question_has_budget(state, qid) for qid in active_qids)


def _increment_question_iterations(state: dict[str, Any]) -> dict[str, int]:
    """Increment per-question counters for active questions. Returns updated dict."""
    q_iters = _get_question_iterations(state)
    for qid in _active_question_ids(state):
        q_iters[qid] = q_iters.get(qid, 0) + 1
    return q_iters


def _min_remaining_budget(state: dict[str, Any]) -> int:
    """Minimum remaining budget across active questions (0 if all exhausted)."""
    max_iter = int(state.get("max_iterations", 5))
    q_iters = _get_question_iterations(state)
    active_qids = _active_question_ids(state)
    if not active_qids:
        return 0
    return max(0, min(max_iter - q_iters.get(qid, 0) for qid in active_qids))


def _max_used_budget(state: dict[str, Any]) -> int:
    """Maximum iterations used by any single question."""
    q_iters = _get_question_iterations(state)
    if not q_iters:
        return 0
    return max(q_iters.values())



def section_reflector_router(state: dict[str, Any]) -> str:
    report = state.get("coverage_report") or {}
    action = report.get("recommended_next_action", "exit")
    has_pending = has_pending_tasks_or_steps(state)

    # Per-question budget replaces the old global iterations check
    has_budget = _any_active_question_has_budget(state)
    all_exhausted = _questions_exhausted(state)

    # 1. needs_human — always goes to human review
    if action == "needs_human":
        return "needs_human"

    # 2. Pending-tasks-and-budget hard guard: when any question has budget,
    #    always execute pending work regardless of LLM exit signal
    if has_budget and has_pending:
        return "run_existing_queue"

    # 3. All active questions exhausted — hard limit
    if all_exhausted:
        return "exit"

    # 4. Respect LLM recommendation for other actions
    if action == "exit":
        return "exit"

    if action == "plan_more":
        return "plan_more"

    if action == "run_existing_queue":
        return "run_existing_queue"

    # 5. Fallback heuristics for robustness
    if wave_complete(state) and has_next_bfs_wave(state):
        return "plan_more"

    if report.get("critical_gaps"):
        return "plan_more"

    # First reflector pass — always plan more to bootstrap
    if _max_used_budget(state) <= 1:
        return "plan_more"

    return "exit"


def section_loop_planner_router(state: dict[str, Any]) -> str:
    if has_pending_tasks_or_steps(state):
        return "run"
    return "exit"


def _count_pending_tasks_steps(state: dict[str, Any]) -> dict[str, int]:
    """Count pending tasks and steps in the research plan."""
    plan_raw = state.get("research_plan") or {}
    if not plan_raw:
        return {"tasks": 0, "steps": 0}
    from tradingagents.equity_research.tasks.section_research.schemas import SectionResearchPlan
    plan = SectionResearchPlan.model_validate(plan_raw)
    pending_tasks = sum(1 for t in plan.tasks if t.status in ("pending", "in_progress"))
    pending_steps = sum(
        1 for t in plan.tasks
        for s in t.steps
        if s.status in ("pending", "in_progress")
    )
    return {"tasks": pending_tasks, "steps": pending_steps}


def _count_pending_todo_items(state: dict[str, Any]) -> int:
    todo_raw = state.get("research_todo_list") or {}
    todo = ResearchTodoList.model_validate(todo_raw) if todo_raw else ResearchTodoList()
    return sum(1 for item in todo.items if item.status in ("pending", "in_progress"))


def _data_availability_signal(view: Any) -> dict[str, int]:
    unavailable_cards = 0
    obtainable_missing_cards = 0
    for card in view.answer_cards.values():
        has_unavailable = any(note.status == "unavailable" for note in card.data_availability_notes)
        has_quant = bool(card.quantified_claims)
        has_sources = bool(card.source_attributions)
        missing_core = (not has_quant) or (not has_sources)
        if has_unavailable:
            unavailable_cards += 1
        elif missing_core:
            obtainable_missing_cards += 1
    return {
        "unavailable_cards": unavailable_cards,
        "obtainable_missing_cards": obtainable_missing_cards,
    }


def create_section_reflector_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    def reflector(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        iterations = int(state.get("iterations", 0)) + 1
        
        # Compute per-question iteration updates early for budget decisions
        new_question_iterations = _increment_question_iterations(state)
        has_budget = _any_active_question_has_budget(state)
        
        try:
            raw_view = state.get("structured_view") or {}
            if raw_view:
                view = task_profile.output_schema.model_validate(raw_view)
            else:
                view = task_profile.empty_view_fn(state.get("ticker", ""))

            search_memory = state.get("search_memory", [])
            memory_summary = ""
            if search_memory:
                memory_summary = build_search_memory_for_prompt(
                    deps, search_memory, compact=False,
                )

            executor_context = state.get("executor_context_snapshot") or format_executor_messages(
                deps,
                list(state.get("messages") or []),
                pending_evidence=list(state.get("pending_evidence") or []),
                active_task=state.get("active_task"),
                active_step=state.get("active_step"),
            )

            system_prompt = build_reflector_system_prompt(task_profile)
            max_iter = int(state.get("max_iterations", task_profile.max_iterations))
            pending = _count_pending_tasks_steps(state)
            pending_todo_items = _count_pending_todo_items(state)
            min_remaining = _min_remaining_budget(state)
            iteration_budget = {
                "current": iterations,
                "max": max_iter,
                "remaining": min_remaining,
                "pending_tasks": pending["tasks"],
                "pending_steps": pending["steps"],
                "pending_todo_items": pending_todo_items,
                "question_iterations": new_question_iterations,
            }
            user_prompt = build_reflector_user_prompt(
                deps,
                view,
                memory_summary,
                state,
                executor_context=executor_context,
                iteration_budget=iteration_budget,
            )
            llm_messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt),
            ]

            def _fallback() -> SectionCoverageEvaluation:
                report = task_profile.default_coverage_report_fn(view)
                return SectionCoverageEvaluation(
                    overall_score=report.overall_score,
                    question_scores=report.question_scores,
                    critical_gaps=report.critical_gaps,
                    recommended_next_action=report.recommended_next_action,
                )

            llm = resolve_research_llm(deps, "quick")
            evaluation: SectionCoverageEvaluation | None = None
            try:
                evaluation = invoke_structured_with_retry(
                    llm,
                    task_profile.coverage_eval_schema,
                    llm_messages,
                    agent_name=f"{task_profile.task_id}_reflector",
                    max_attempts=_max_retries(deps),
                    fallback=_fallback,
                )
                report = task_profile.evaluation_to_report_fn(evaluation)
            except StructuredOutputUnsupported:
                report = task_profile.default_coverage_report_fn(view)

            plan_completion = compute_plan_completion(state.get("research_plan") or {})
            from tradingagents.equity_research.tasks.section_research.schemas import PlanCompletion
            report.plan_completion = PlanCompletion.model_validate(plan_completion)

            availability = _data_availability_signal(view)
            availability_retry_count = int(state.get("_data_availability_retry_count", 0))
            
            # Use per-question budget for decisions
            if pending_todo_items > 0 and has_budget:
                report.recommended_next_action = "run_existing_queue"
                report.routing_decision = "continue"
                report.data_quality_issues.append({
                    "type": "pending_todo_items",
                    "severity": "low",
                    "message": f"{pending_todo_items} todo items still pending/in_progress.",
                })
            elif has_pending_tasks_or_steps(state) and has_budget:
                report.recommended_next_action = "run_existing_queue"
                report.routing_decision = "continue"
            elif not has_budget and not has_pending_tasks_or_steps(state):
                report.recommended_next_action = "exit"
                report.routing_decision = "exit"
            elif (
                report.overall_score >= task_profile.coverage_threshold
                and not report.critical_gaps
                and not has_pending_tasks_or_steps(state)
            ):
                report.recommended_next_action = "exit"
                report.routing_decision = "exit"
            else:
                report.routing_decision = "continue"

            # Data-availability gate:
            # - If required data appears obtainable but missing, force one extra cycle.
            # - If still missing after one retry, allow exit only when plan is complete.
            if availability["obtainable_missing_cards"] > 0 and has_budget:
                if availability_retry_count < 1:
                    report.recommended_next_action = (
                        "run_existing_queue" if has_pending_tasks_or_steps(state) else "plan_more"
                    )
                    report.routing_decision = "continue"
                elif not has_pending_tasks_or_steps(state):
                    report.recommended_next_action = "exit"
                    report.routing_decision = "exit"
                    report.data_quality_issues.append({
                        "type": "data_availability_unresolved",
                        "severity": "medium",
                        "message": (
                            "Structured quantitative/source fields remained incomplete "
                            "after one retry cycle."
                        ),
                    })

            view.coverage_score = report.overall_score
            coverage_history = list(state.get("coverage_history", []))
            coverage_history.append(report.model_dump())

            answer_cards = dict(state.get("answer_cards") or {})
            for qid, card in view.answer_cards.items():
                answer_cards[qid] = card.model_dump()

            completed_todo_ids = list(getattr(evaluation, "completed_todo_ids", None) or []) if evaluation else []
            todo_update: dict[str, Any] = {}
            if completed_todo_ids:
                todo_raw = state.get("research_todo_list") or {}
                todo_list = ResearchTodoList.model_validate(todo_raw) if todo_raw else ResearchTodoList()
                marked: set[str] = set()
                for item in todo_list.items:
                    if item.item_id in completed_todo_ids and item.status in ("pending", "in_progress"):
                        item.status = "done"
                        item.completed_at = datetime.utcnow().isoformat()
                        item.source = "reflector"
                        marked.add(item.item_id)
                if marked:
                    todo_list.version += 1
                    todo_update = {"research_todo_list": todo_list.model_dump()}

            updates: dict[str, Any] = {
                "coverage_report": report.model_dump(),
                "coverage_history": coverage_history,
                "structured_view": view.model_dump(),
                "answer_cards": answer_cards,
                "iterations": iterations,
                "question_iterations": new_question_iterations,
                "unresolved_gaps": [g.get("gap", str(g)) for g in report.critical_gaps],
                "status": "sufficient" if report.recommended_next_action == "exit" else "continue",
                "_data_availability_retry_count": (
                    availability_retry_count + 1
                    if availability["obtainable_missing_cards"] > 0 and availability_retry_count < 1
                    else 0
                ),
            }
            updates.update(todo_update)
            merged_for_todo_count = {**state, **updates}
            updates["pending_todo_items"] = _count_pending_todo_items(merged_for_todo_count)
            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_reflector", {
                "overall_score": report.overall_score,
                "action": report.recommended_next_action,
            }))
            return updates
        except Exception as exc:
            errors.append(f"section_reflector: {exc}")
            return {
                "errors": errors,
                "iterations": iterations,
                "question_iterations": new_question_iterations,
                "coverage_report": {
                    "recommended_next_action": "exit",
                    "routing_decision": "exit",
                },
            }

    return reflector
