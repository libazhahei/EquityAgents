"""Sync SectionResearchPlan steps to ResearchTodoList."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchTodoItem,
    ResearchTodoList,
    SectionResearchPlan,
)


def _new_item_id() -> str:
    return f"todo_{uuid.uuid4().hex[:8]}"


def plan_to_todo_sync(
    plan: SectionResearchPlan | dict[str, Any],
    *,
    existing: ResearchTodoList | dict[str, Any] | None = None,
    incremental: bool = False,
) -> ResearchTodoList:
    if isinstance(plan, dict):
        plan = SectionResearchPlan.model_validate(plan)
    if existing is None:
        todo = ResearchTodoList(
            list_id=f"todo_{plan.section_id}",
            section_id=plan.section_id,
        )
    elif isinstance(existing, dict):
        todo = ResearchTodoList.model_validate(existing)
    else:
        todo = existing

    existing_keys = {
        (item.task_id, item.step_id)
        for item in todo.items
        if item.task_id and item.step_id
    }

    order = plan.execution_order or [t.task_id for t in plan.tasks]
    task_by_id = {t.task_id: t for t in plan.tasks}
    new_items: list[ResearchTodoItem] = list(todo.items) if incremental else []

    for task_id in order:
        task = task_by_id.get(task_id)
        if not task:
            continue
        for step in sorted(task.steps, key=lambda s: s.order):
            key = (task.task_id, step.step_id)
            if incremental and key in existing_keys:
                continue
            new_items.append(
                ResearchTodoItem(
                    item_id=_new_item_id(),
                    title=step.description[:120] or f"{task.objective[:80]}",
                    description=step.expected_output or step.description,
                    question_id=task.question_id,
                    task_id=task.task_id,
                    step_id=step.step_id,
                    action=step.action,
                    priority=task.priority,
                    status="pending" if step.status == "pending" else step.status,  # type: ignore[arg-type]
                    source="planner",
                    tool_hints=list(step.tool_hints),
                    created_at=datetime.utcnow().isoformat(),
                )
            )

    if not incremental:
        todo.items = new_items
    else:
        todo.items = new_items
    todo.version += 1
    return todo


def has_pending_tasks_or_steps(state: dict[str, Any]) -> bool:
    todo_raw = state.get("research_todo_list") or {}
    todo = ResearchTodoList.model_validate(todo_raw) if todo_raw else ResearchTodoList()
    if any(item.status in ("pending", "in_progress") for item in todo.items):
        return True
    plan_raw = state.get("research_plan") or {}
    if not plan_raw:
        return bool(state.get("task_queue"))
    plan = SectionResearchPlan.model_validate(plan_raw)
    for task in plan.tasks:
        if task.status in ("pending", "in_progress"):
            return True
        if any(s.status in ("pending", "in_progress") for s in task.steps):
            return True
    return bool(state.get("task_queue"))


def pick_active_task_and_step(state: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    plan_raw = state.get("research_plan") or {}
    if not plan_raw:
        return state.get("active_task"), state.get("active_step")
    plan = SectionResearchPlan.model_validate(plan_raw)
    order = plan.execution_order or [t.task_id for t in plan.tasks]
    task_by_id = {t.task_id: t for t in plan.tasks}
    for task_id in order:
        task = task_by_id.get(task_id)
        if not task or task.status in ("done", "blocked"):
            continue
        for step in sorted(task.steps, key=lambda s: s.order):
            if step.status in ("pending", "in_progress"):
                return task.model_dump(), step.model_dump()
    return None, None
