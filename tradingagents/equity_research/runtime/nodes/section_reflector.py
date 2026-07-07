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


def section_reflector_router(state: dict[str, Any]) -> str:
    report = state.get("coverage_report") or {}
    action = report.get("recommended_next_action", "exit")
    iterations = int(state.get("iterations", 0))
    max_iter = int(state.get("max_iterations", 5))

    # Hard safety valve: force exit when iterations budget is exhausted.
    # Prevents the LangGraph recursion limit from being hit before the
    # reflector node can set routing_decision="exit".
    if iterations >= max_iter:
        return "exit"

    if action == "needs_human":
        return "needs_human"

    # When the reflector node explicitly decided to exit (e.g. coverage
    # threshold met or max_iter reached inside the node), respect it
    # unconditionally instead of redirecting to BFS plan_more.
    if report.get("routing_decision") == "exit" or action == "exit":
        return "exit"

    # Continue executing pending plan steps / todo items.
    if has_pending_tasks_or_steps(state):
        return "run_existing_queue"

    # BFS wave progression: current wave done, more waves available.
    if wave_complete(state) and has_next_bfs_wave(state):
        return "plan_more"

    if report.get("critical_gaps"):
        return "plan_more"

    # First iteration with no pending work — try planning more.
    if iterations <= 1:
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


def create_section_reflector_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    def reflector(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        iterations = int(state.get("iterations", 0)) + 1
        try:
            raw_view = state.get("structured_view") or {}
            if raw_view:
                view = task_profile.output_schema.model_validate(raw_view)
            else:
                view = task_profile.empty_view_fn(state.get("ticker", ""))

            search_memory = state.get("search_memory", [])
            memory_summary = ""
            if search_memory:
                memory_summary = (
                    f"\nSearch history:\n"
                    f"{build_search_memory_for_prompt(deps, search_memory)}\n"
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
            iteration_budget = {
                "current": iterations,
                "max": max_iter,
                "remaining": max(0, max_iter - iterations),
                "pending_tasks": pending["tasks"],
                "pending_steps": pending["steps"],
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

            max_iter = int(state.get("max_iterations", task_profile.max_iterations))
            if has_pending_tasks_or_steps(state) and iterations < max_iter:
                if report.recommended_next_action == "exit" and report.overall_score < task_profile.coverage_threshold:
                    report.recommended_next_action = "run_existing_queue"
                    report.routing_decision = "continue"
            elif iterations >= max_iter:
                report.recommended_next_action = "exit"
                report.routing_decision = "exit"
            elif report.overall_score >= task_profile.coverage_threshold and not report.critical_gaps:
                report.recommended_next_action = "exit"
                report.routing_decision = "exit"
            else:
                report.routing_decision = "continue"

            view.coverage_score = report.overall_score
            coverage_history = list(state.get("coverage_history", []))
            coverage_history.append(report.model_dump())

            answer_cards = dict(state.get("answer_cards") or {})
            for qid, card in view.answer_cards.items():
                answer_cards[qid] = card.model_dump()

            completed_todo_ids = list(getattr(evaluation, "completed_todo_ids", None) or [])
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
                "unresolved_gaps": [g.get("gap", str(g)) for g in report.critical_gaps],
                "status": "sufficient" if report.recommended_next_action == "exit" else "continue",
            }
            updates.update(todo_update)
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
                "coverage_report": {
                    "recommended_next_action": "exit",
                    "routing_decision": "exit",
                },
            }

    return reflector
