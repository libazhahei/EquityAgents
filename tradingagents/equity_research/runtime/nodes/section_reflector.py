"""Section research reflector — plan-aware coverage evaluation."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.search_memory import build_search_memory_for_prompt
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.tasks.section_research.merge import compute_plan_completion
from tradingagents.equity_research.tasks.section_research.schemas import SectionCoverageEvaluation
from tradingagents.equity_research.tasks.section_research.bfs_todos import (
    has_next_bfs_wave,
    wave_complete,
)
from tradingagents.equity_research.tasks.section_research.todo_sync import has_pending_tasks_or_steps


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def section_reflector_router(state: dict[str, Any]) -> str:
    report = state.get("coverage_report") or {}
    action = report.get("recommended_next_action", "exit")
    if action == "needs_human":
        return "needs_human"
    if action == "exit" or report.get("routing_decision") == "exit":
        if wave_complete(state) and not has_next_bfs_wave(state):
            return "exit"
        if has_next_bfs_wave(state) and wave_complete(state):
            return "plan_more"
    if has_pending_tasks_or_steps(state):
        return "run_existing_queue"
    if wave_complete(state) and has_next_bfs_wave(state):
        return "plan_more"
    if report.get("critical_gaps"):
        return "plan_more"
    iterations = int(state.get("iterations", 0))
    if iterations <= 1 and not has_pending_tasks_or_steps(state):
        return "plan_more"
    return "exit"


def section_loop_planner_router(state: dict[str, Any]) -> str:
    if has_pending_tasks_or_steps(state):
        return "run"
    return "exit"


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

            prompt = task_profile.build_reflector_prompt(deps, view, memory_summary, state)

            def _fallback() -> SectionCoverageEvaluation:
                report = task_profile.default_coverage_report_fn(view)
                return SectionCoverageEvaluation(
                    overall_score=report.overall_score,
                    question_scores=report.question_scores,
                    critical_gaps=report.critical_gaps,
                    recommended_next_action=report.recommended_next_action,
                )

            try:
                evaluation = invoke_structured_with_retry(
                    deps.quick_llm,
                    task_profile.coverage_eval_schema,
                    prompt,
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

            updates: dict[str, Any] = {
                "coverage_report": report.model_dump(),
                "coverage_history": coverage_history,
                "structured_view": view.model_dump(),
                "answer_cards": answer_cards,
                "iterations": iterations,
                "unresolved_gaps": [g.get("gap", str(g)) for g in report.critical_gaps],
                "status": "sufficient" if report.recommended_next_action == "exit" else "continue",
            }
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
