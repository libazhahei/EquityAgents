"""Section research planner nodes — multi-step research plans."""

from __future__ import annotations

import copy
import uuid
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.tasks.section_research.bfs_todos import (
    activate_wave_tasks,
    append_wave_todos,
    bfs_levels,
    current_bfs_wave,
    has_next_bfs_wave,
    wave_complete,
)
from tradingagents.equity_research.tasks.section_research.planning import (
    build_fallback_plan,
    expand_outline_to_plan,
    expand_task_outlines,
)
from tradingagents.equity_research.state.blackboard import format_blackboard_for_prompt

from tradingagents.equity_research.tasks.section_research.schemas import (
    SectionResearchPlan,
    SectionResearchPlanOutlineLLMOutput,
    SectionReplanLLMOutput,
)
from tradingagents.equity_research.tasks.section_research.todo_sync import (
    has_pending_tasks_or_steps,
    pick_active_task_and_step,
)


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _task_queue_from_plan(plan: SectionResearchPlan) -> list[dict]:
    order = plan.execution_order or [t.task_id for t in plan.tasks]
    by_id = {t.task_id: t for t in plan.tasks}
    return [by_id[tid].model_dump() for tid in order if tid in by_id]


def _ensure_bfs_levels(state: dict[str, Any]) -> list[list[str]]:
    levels = state.get("bfs_levels") or []
    if levels:
        return levels
    question_graph = state.get("question_graph") or {}
    return bfs_levels(question_graph)


def _apply_plan_to_state(
    plan: SectionResearchPlan,
    state: dict[str, Any],
    *,
    incremental_todo: bool = False,
    wave_index: int | None = None,
) -> dict[str, Any]:
    levels = _ensure_bfs_levels(state)
    wave_idx = current_bfs_wave(state) if wave_index is None else wave_index
    wave_qids = levels[wave_idx] if levels and wave_idx < len(levels) else [
        t.question_id for t in plan.tasks[:5]
    ]

    activated = activate_wave_tasks(plan, wave_qids)
    plan_dump = activated.model_dump()

    todo = append_wave_todos(
        activated,
        wave_qids,
        state.get("research_todo_list"),
        wave_index=wave_idx,
        question_graph=state.get("question_graph"),
        incremental=incremental_todo,
    )

    working = {
        **state,
        "research_plan": plan_dump,
        "research_todo_list": todo.model_dump(),
        "bfs_levels": levels,
        "bfs_wave_index": wave_idx,
    }
    active_task, active_step = pick_active_task_and_step(working)
    if active_task and active_task.get("status") == "pending":
        active_task = {**active_task, "status": "in_progress"}
    if active_step and active_step.get("status") == "pending":
        active_step = {**active_step, "status": "in_progress"}
    return {
        "research_plan": plan_dump,
        "research_todo_list": todo.model_dump(),
        "task_queue": _task_queue_from_plan(activated),
        "active_task": active_task,
        "active_step": active_step,
        "bfs_levels": levels,
        "bfs_wave_index": wave_idx,
    }


def _advance_bfs_wave(state: dict[str, Any], plan: SectionResearchPlan) -> dict[str, Any] | None:
    if not wave_complete(state) or not has_next_bfs_wave(state):
        return None
    next_wave = current_bfs_wave(state) + 1
    return _apply_plan_to_state(plan, state, incremental_todo=True, wave_index=next_wave)


def create_section_planner_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    mode: str = "initial",
):
    is_initial = mode == "initial"
    prompt_builder = (
        task_profile.build_initial_planner_prompt
        if is_initial
        else task_profile.build_loop_planner_prompt
    )
    agent_name = f"{task_profile.task_id}_{'initial' if is_initial else 'loop'}_planner"

    def planner(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        section_id = str(state.get("section_id", ""))
        brief_raw = state.get("research_brief") or {}

        try:
            if is_initial:
                plan: SectionResearchPlan
                llm = resolve_research_llm(deps, "deep")
                try:
                    prompt = prompt_builder(deps, state)
                    # Inject blackboard context
                    bb = state.get("blackboard") or []
                    if bb:
                        bb_text = format_blackboard_for_prompt(bb, max_items=8, section_id=state.get("section_id"))
                        if bb_text:
                            prompt = prompt + "\n\n" + bb_text
                    llm_out = invoke_structured_with_retry(
                        llm,
                        SectionResearchPlanOutlineLLMOutput,
                        prompt,
                        agent_name=agent_name,
                        max_attempts=_max_retries(deps),
                        fallback=lambda: SectionResearchPlanOutlineLLMOutput(),
                    )
                    if llm_out.tasks:
                        plan = expand_outline_to_plan(
                            llm_out,
                            brief_raw,
                            section_id=section_id,
                            plan_id=f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
                        )
                    else:
                        raise StructuredOutputUnsupported("empty plan")
                except (StructuredOutputUnsupported, Exception) as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Initial planner failed: {e.with_traceback(e.__traceback__)}")
                    plan = build_fallback_plan(brief_raw, section_id=section_id)

                updates = _apply_plan_to_state(plan, state, wave_index=0)
                if not has_pending_tasks_or_steps({**state, **updates}):
                    plan = build_fallback_plan(brief_raw, section_id=section_id)
                    updates = _apply_plan_to_state(plan, state, wave_index=0)

                updates.update(deps.trace({**state, **updates}, agent_name, {
                    "tasks": len(plan.tasks),
                    "steps": sum(len(t.steps) for t in plan.tasks),
                    "bfs_wave": updates.get("bfs_wave_index", 0),
                }))
                return updates

            # Loop replan — wave advance takes priority over gap replan
            current = SectionResearchPlan.model_validate(state.get("research_plan") or {})
            wave_advance = _advance_bfs_wave(state, current)
            if wave_advance is not None:
                wave_advance["plan_history"] = list(state.get("plan_history", []))
                wave_advance.update(deps.trace({**state, **wave_advance}, agent_name, {
                    "mode": "wave_advance",
                    "bfs_wave": wave_advance.get("bfs_wave_index"),
                }))
                return wave_advance

            history = list(current.plan_history)
            history.append(copy.deepcopy(current.model_dump()))

            try:
                prompt = prompt_builder(deps, state)
                # Inject blackboard context
                bb = state.get("blackboard") or []
                if bb:
                    bb_text = format_blackboard_for_prompt(bb, max_items=8, section_id=state.get("section_id"))
                    if bb_text:
                        prompt = prompt + "\n\n" + bb_text
                llm = resolve_research_llm(deps, "deep")
                replan = invoke_structured_with_retry(
                    llm,
                    SectionReplanLLMOutput,
                    prompt,
                    agent_name=agent_name,
                    max_attempts=_max_retries(deps),
                    fallback=lambda: SectionReplanLLMOutput(),
                )
                tasks = list(current.tasks)
                expanded_new = expand_task_outlines(replan.new_tasks, brief_raw)
                for new_task in expanded_new:
                    tasks.append(new_task)
                for append in replan.append_steps:
                    task_id = append.get("task_id")
                    for task in tasks:
                        if task.task_id == task_id and append.get("step"):
                            from tradingagents.equity_research.tasks.section_research.schemas import ResearchStep
                            task.steps.append(ResearchStep.model_validate(append["step"]))
                execution_order = list(current.execution_order)
                for t in expanded_new:
                    execution_order.append(t.task_id)
                current = SectionResearchPlan(
                    plan_id=current.plan_id,
                    section_id=current.section_id,
                    version=current.version + 1,
                    tasks=tasks,
                    execution_order=execution_order,
                    plan_rationale=replan.rationale or current.plan_rationale,
                    plan_history=history,
                )
            except Exception:
                current = SectionResearchPlan(
                    **{**current.model_dump(), "version": current.version + 1, "plan_history": history},
                )

            updates = _apply_plan_to_state(
                current, state, incremental_todo=True, wave_index=current_bfs_wave(state),
            )
            updates["plan_history"] = history
            updates["query_queue"] = []
            updates.update(deps.trace({**state, **updates}, agent_name, {
                "plan_version": current.version,
                "tasks": len(current.tasks),
                "mode": "gap_replan",
            }))
            return updates
        except Exception as exc:
            errors.append(f"{agent_name}: {exc}")
            if is_initial:
                plan = build_fallback_plan(brief_raw, section_id=section_id)
                updates = _apply_plan_to_state(plan, state, wave_index=0)
                updates["errors"] = errors
                return updates
            return {"errors": errors, "query_queue": []}

    return planner


def section_initial_planner_router(state: dict[str, Any]) -> str:
    if has_pending_tasks_or_steps(state):
        return "executor"
    return "loop_planner"
