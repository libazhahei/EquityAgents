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
    expand_outline_to_plan,
    expand_task_outlines,
    merge_plans,
    missing_wave_question_ids,
)
from tradingagents.equity_research.state.blackboard import format_blackboard_for_prompt

from tradingagents.equity_research.tasks.section_research.prompts import (
    build_wave_task_supplement_prompt,
)
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


def _wave_qids_for_index(state: dict[str, Any], wave_index: int) -> list[str]:
    levels = _ensure_bfs_levels(state)
    if levels and 0 <= wave_index < len(levels):
        return [str(qid) for qid in levels[wave_index]]
    return []


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


def _inject_blackboard(prompt: str, state: dict[str, Any]) -> str:
    bb = state.get("blackboard") or []
    if not bb:
        return prompt
    bb_text = format_blackboard_for_prompt(bb, max_items=8, section_id=state.get("section_id"))
    if bb_text:
        return prompt + "\n\n" + bb_text
    return prompt


def _invoke_plan_outline(
    deps: EquityResearchDeps,
    llm: Any,
    prompt: str,
    *,
    agent_name: str,
) -> SectionResearchPlanOutlineLLMOutput:
    return invoke_structured_with_retry(
        llm,
        SectionResearchPlanOutlineLLMOutput,
        prompt,
        agent_name=agent_name,
        max_attempts=_max_retries(deps),
        fallback=lambda: SectionResearchPlanOutlineLLMOutput(),
    )


def _supplement_missing_wave_tasks(
    deps: EquityResearchDeps,
    llm: Any,
    state: dict[str, Any],
    plan: SectionResearchPlan,
    *,
    brief_raw: dict[str, Any],
    section_id: str,
    wave_qids: list[str],
    agent_name: str,
) -> SectionResearchPlan:
    """If wave questions are missing tasks, run a second LLM round to add only those."""
    missing = missing_wave_question_ids(plan, wave_qids)
    if not missing:
        return plan

    supplement_prompt = build_wave_task_supplement_prompt(
        deps,
        state,
        missing_qids=missing,
        existing_task_qids=[t.question_id for t in plan.tasks],
    )
    supplement_prompt = _inject_blackboard(supplement_prompt, state)
    try:
        llm_out = _invoke_plan_outline(
            deps, llm, supplement_prompt, agent_name=f"{agent_name}_wave_supplement",
        )
        if not llm_out.tasks:
            return plan
        extra = expand_outline_to_plan(
            llm_out,
            brief_raw,
            section_id=section_id,
            plan_id=plan.plan_id,
        )
        # Keep only tasks for still-missing qids
        missing_set = set(missing)
        filtered_tasks = [t for t in extra.tasks if t.question_id in missing_set]
        if not filtered_tasks:
            return plan
        extra = SectionResearchPlan(
            plan_id=extra.plan_id,
            section_id=extra.section_id,
            version=extra.version,
            tasks=filtered_tasks,
            execution_order=[t.task_id for t in filtered_tasks],
            plan_rationale=extra.plan_rationale,
        )
        return merge_plans(plan, extra)
    except Exception:
        return plan


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
                levels = _ensure_bfs_levels(state)
                # Ensure bfs_levels are on state for prompt builders
                working_state = {**state, "bfs_levels": levels, "bfs_wave_index": 0}
                wave0 = _wave_qids_for_index(working_state, 0)
                llm = resolve_research_llm(deps, "deep")
                plan: SectionResearchPlan | None = None

                try:
                    assert prompt_builder is not None
                    prompt = _inject_blackboard(prompt_builder(deps, working_state), working_state)
                    llm_out = _invoke_plan_outline(
                        deps, llm, prompt, agent_name=agent_name,
                    )
                    if not llm_out.tasks:
                        raise StructuredOutputUnsupported("empty plan")
                    plan = expand_outline_to_plan(
                        llm_out,
                        brief_raw,
                        section_id=section_id,
                        plan_id=f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
                    )
                except (StructuredOutputUnsupported, Exception) as e:
                    import traceback
                    traceback.print_exc()
                    print(f"Initial planner failed, retrying full round: {e}")
                    # Fallback = another full planning round (not rule-based fill)
                    try:
                        assert prompt_builder is not None
                        retry_prompt = _inject_blackboard(
                            prompt_builder(deps, working_state), working_state,
                        )
                        retry_prompt += (
                            "\n\nPREVIOUS ATTEMPT FAILED OR RETURNED AN EMPTY/INVALID PLAN. "
                            "Retry carefully. Emit exactly one task per CURRENT WAVE checklist "
                            f"question_id ({len(wave0)} tasks)."
                        )
                        llm_out = _invoke_plan_outline(
                            deps, llm, retry_prompt, agent_name=f"{agent_name}_retry",
                        )
                        if not llm_out.tasks:
                            raise StructuredOutputUnsupported("empty plan on retry")
                        plan = expand_outline_to_plan(
                            llm_out,
                            brief_raw,
                            section_id=section_id,
                            plan_id=f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
                        )
                    except Exception as retry_exc:
                        errors.append(f"{agent_name}: {e}; retry: {retry_exc}")
                        return {"errors": errors, "query_queue": []}

                assert plan is not None
                # Supplement round for any still-missing wave questions
                plan = _supplement_missing_wave_tasks(
                    deps,
                    llm,
                    working_state,
                    plan,
                    brief_raw=brief_raw,
                    section_id=section_id,
                    wave_qids=wave0,
                    agent_name=agent_name,
                )

                updates = _apply_plan_to_state(plan, working_state, wave_index=0)
                if not has_pending_tasks_or_steps({**working_state, **updates}):
                    # Still empty after supplement: one more full+supplement attempt
                    try:
                        assert prompt_builder is not None
                        prompt = _inject_blackboard(
                            prompt_builder(deps, working_state), working_state,
                        )
                        prompt += (
                            "\n\nThe plan produced no runnable tasks. "
                            f"Emit exactly {len(wave0)} tasks covering every wave question_id."
                        )
                        llm_out = _invoke_plan_outline(
                            deps, llm, prompt, agent_name=f"{agent_name}_empty_queue_retry",
                        )
                        if llm_out.tasks:
                            plan = expand_outline_to_plan(
                                llm_out,
                                brief_raw,
                                section_id=section_id,
                                plan_id=f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
                            )
                            plan = _supplement_missing_wave_tasks(
                                deps,
                                llm,
                                working_state,
                                plan,
                                brief_raw=brief_raw,
                                section_id=section_id,
                                wave_qids=wave0,
                                agent_name=agent_name,
                            )
                            updates = _apply_plan_to_state(plan, working_state, wave_index=0)
                    except Exception as empty_exc:
                        errors.append(f"{agent_name}_empty_queue_retry: {empty_exc}")

                if errors:
                    updates["errors"] = errors
                updates.update(deps.trace({**working_state, **updates}, agent_name, {
                    "tasks": len(plan.tasks),
                    "steps": sum(len(t.steps) for t in plan.tasks),
                    "bfs_wave": updates.get("bfs_wave_index", 0),
                    "missing_after_supplement": missing_wave_question_ids(plan, wave0),
                }))
                return updates

            # Loop replan — wave advance takes priority over gap replan
            current = SectionResearchPlan.model_validate(state.get("research_plan") or {})
            wave_advance = _advance_bfs_wave(state, current)
            if wave_advance is not None:
                # After activating next wave, LLM-supplement any missing next-wave tasks
                next_idx = int(wave_advance.get("bfs_wave_index", current_bfs_wave(state) + 1))
                next_qids = _wave_qids_for_index({**state, **wave_advance}, next_idx)
                llm = resolve_research_llm(deps, "deep")
                plan_after = SectionResearchPlan.model_validate(
                    wave_advance.get("research_plan") or current.model_dump(),
                )
                plan_after = _supplement_missing_wave_tasks(
                    deps,
                    llm,
                    {**state, **wave_advance},
                    plan_after,
                    brief_raw=brief_raw,
                    section_id=section_id,
                    wave_qids=next_qids,
                    agent_name=agent_name,
                )
                if missing_wave_question_ids(plan_after, next_qids) != missing_wave_question_ids(
                    current, next_qids,
                ) or len(plan_after.tasks) != len(current.tasks):
                    wave_advance = _apply_plan_to_state(
                        plan_after, {**state, **wave_advance},
                        incremental_todo=True, wave_index=next_idx,
                    )
                wave_advance["plan_history"] = list(state.get("plan_history", []))
                wave_advance.update(deps.trace({**state, **wave_advance}, agent_name, {
                    "mode": "wave_advance",
                    "bfs_wave": wave_advance.get("bfs_wave_index"),
                }))
                return wave_advance

            history = list(current.plan_history)
            history.append(copy.deepcopy(current.model_dump()))

            try:
                assert prompt_builder is not None
                prompt = _inject_blackboard(prompt_builder(deps, state), state)
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
            return {"errors": errors, "query_queue": []}

    return planner


def section_initial_planner_router(state: dict[str, Any]) -> str:
    if has_pending_tasks_or_steps(state):
        return "executor"
    return "loop_planner"
