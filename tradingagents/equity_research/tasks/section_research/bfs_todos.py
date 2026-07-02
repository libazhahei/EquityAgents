"""BFS wave-based todo expansion for section research."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchTodoItem,
    ResearchTodoList,
    ResearchTask,
    SectionResearchPlan,
)


def _new_item_id() -> str:
    return f"todo_{uuid.uuid4().hex[:8]}"


def bfs_levels(question_graph: dict[str, Any]) -> list[list[str]]:
    """Return executable question ids grouped by BFS depth (level-0 root excluded)."""
    nodes = question_graph.get("nodes") or {}
    if not nodes:
        return []

    by_id: dict[str, dict[str, Any]] = {}
    for qid, node in nodes.items():
        if not qid:
            continue
        by_id[str(qid)] = dict(node) if isinstance(node, dict) else {}

    if not by_id:
        return []

    roots = [
        qid for qid, node in by_id.items()
        if int(node.get("level", 0)) == 0 or node.get("parent_id") in (None, "", qid)
    ]
    if not roots:
        min_level = min(int(n.get("level", 1)) for n in by_id.values())
        roots = [qid for qid, n in by_id.items() if int(n.get("level", 0)) == min_level]

    children: dict[str, list[str]] = {qid: [] for qid in by_id}
    for qid, node in by_id.items():
        parent = node.get("parent_id")
        if parent and str(parent) in children and str(parent) != qid:
            children[str(parent)].append(qid)

    levels: list[list[str]] = []
    visited: set[str] = set()
    frontier = list(roots)
    while frontier:
        wave: list[str] = []
        next_frontier: list[str] = []
        for qid in frontier:
            if qid in visited:
                continue
            visited.add(qid)
            level = int(by_id[qid].get("level", 0))
            if level == 0:
                next_frontier.extend(children.get(qid, []))
                continue
            wave.append(qid)
            next_frontier.extend(children.get(qid, []))
        if wave:
            wave.sort(key=lambda q: (int(by_id[q].get("priority", 99)), q))
            levels.append(wave)
        frontier = next_frontier

    if not levels:
        level_1 = [
            qid for qid, n in by_id.items()
            if int(n.get("level", 0)) >= 1
        ]
        if level_1:
            level_1.sort(key=lambda q: (int(by_id[q].get("priority", 99)), q))
            levels.append(level_1)

    return levels


def current_bfs_wave(state: dict[str, Any]) -> int:
    return int(state.get("bfs_wave_index", 0))


def wave_question_ids(state: dict[str, Any]) -> list[str]:
    levels = state.get("bfs_levels") or []
    idx = current_bfs_wave(state)
    if not levels or idx >= len(levels):
        return []
    return list(levels[idx])


def has_next_bfs_wave(state: dict[str, Any]) -> bool:
    levels = state.get("bfs_levels") or []
    return current_bfs_wave(state) + 1 < len(levels)


def tasks_for_wave(
    plan: SectionResearchPlan | dict[str, Any],
    question_ids: list[str],
) -> list[ResearchTask]:
    if isinstance(plan, dict):
        plan = SectionResearchPlan.model_validate(plan)
    if not question_ids:
        return []
    qset = set(question_ids)
    order = plan.execution_order or [t.task_id for t in plan.tasks]
    task_by_id = {t.task_id: t for t in plan.tasks}
    matched: list[ResearchTask] = []
    for task_id in order:
        task = task_by_id.get(task_id)
        if task and task.question_id in qset:
            matched.append(task)
    for task in plan.tasks:
        if task.question_id in qset and task not in matched:
            matched.append(task)
    return matched


def _node_level(question_graph: dict[str, Any], question_id: str) -> int:
    nodes = question_graph.get("nodes") or {}
    node = nodes.get(question_id) or {}
    return int(node.get("level", 1))


def append_wave_todos(
    plan: SectionResearchPlan | dict[str, Any],
    question_ids: list[str],
    existing: ResearchTodoList | dict[str, Any] | None,
    *,
    wave_index: int = 0,
    question_graph: dict[str, Any] | None = None,
    incremental: bool = True,
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

    wave_tasks = tasks_for_wave(plan, question_ids)
    new_items: list[ResearchTodoItem] = list(todo.items) if incremental else []

    for task in wave_tasks:
        node_level = _node_level(question_graph or {}, task.question_id)
        priority = max(10, 100 - wave_index * 10 - node_level)
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
                    priority=priority,
                    status="pending" if step.status == "pending" else step.status,  # type: ignore[arg-type]
                    source="planner",
                    tool_hints=list(step.tool_hints),
                    created_at=datetime.utcnow().isoformat(),
                )
            )

    todo.items = new_items
    todo.version += 1
    return todo


def wave_complete(state: dict[str, Any]) -> bool:
    """True when all tasks for the current BFS wave are done/skipped."""
    question_ids = set(wave_question_ids(state))
    if not question_ids:
        return True

    plan_raw = state.get("research_plan") or {}
    if not plan_raw:
        return True

    plan = SectionResearchPlan.model_validate(plan_raw)
    wave_tasks = tasks_for_wave(plan, list(question_ids))
    if not wave_tasks:
        return True

    for task in wave_tasks:
        if task.status in ("pending", "in_progress"):
            return False
        for step in task.steps:
            if step.status in ("pending", "in_progress"):
                return False
    return True


def activate_wave_tasks(
    plan: SectionResearchPlan | dict[str, Any],
    question_ids: list[str],
) -> SectionResearchPlan:
    """Mark non-wave tasks as blocked so executor focuses on current wave only."""
    if isinstance(plan, dict):
        plan = SectionResearchPlan.model_validate(plan)
    qset = set(question_ids)
    for task in plan.tasks:
        if task.question_id not in qset and task.status == "pending":
            task.status = "blocked"
        elif task.question_id in qset and task.status == "blocked":
            task.status = "pending"
    return plan
