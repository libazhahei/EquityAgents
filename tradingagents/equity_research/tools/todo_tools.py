"""Pure functions for research todo list CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchTodoItem,
    ResearchTodoList,
    TodoStatus,
)


def _new_item_id() -> str:
    return f"todo_{uuid.uuid4().hex[:8]}"


def _get_todo_list(state: dict[str, Any]) -> ResearchTodoList:
    raw = state.get("research_todo_list") or {}
    section_id = str(state.get("section_id", raw.get("section_id", "")))
    if not raw:
        return ResearchTodoList(list_id=f"todo_{section_id}", section_id=section_id)
    return ResearchTodoList.model_validate(raw)


def list_research_todos(
    state: dict[str, Any],
    *,
    status: str | None = None,
    question_id: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    todo = _get_todo_list(state)
    items = list(todo.items)
    
    if status:
        items = [i for i in items if i.status == status]
    if question_id:
        items = [i for i in items if i.question_id == question_id]
    items.sort(key=lambda i: i.priority, reverse=True)
    total = len(items)
    if limit is not None:
        items = items[:limit]
    return {
        "items": [i.model_dump() for i in items],
        "total": total,
        "remaining": total - len(items),
    }


def add_research_todo(
    state: dict[str, Any],
    *,
    title: str,
    description: str = "",
    question_id: str | None = None,
    task_id: str | None = None,
    step_id: str | None = None,
    action: str | None = None,
    priority: int = 50,
    tool_hints: list[str] | None = None,
    source: str = "executor",
) -> dict[str, Any]:
    todo = _get_todo_list(state)
    item = ResearchTodoItem(
        item_id=_new_item_id(),
        title=title,
        description=description,
        question_id=question_id,
        task_id=task_id,
        step_id=step_id,
        action=action,
        priority=priority,
        source=source,  # type: ignore[arg-type]
        tool_hints=list(tool_hints or []),
        created_at=datetime.utcnow().isoformat(),
    )
    todo.items.append(item)
    todo.version += 1
    return {
        "added_item": item.model_dump(),
    }


def remove_research_todo(
    state: dict[str, Any],
    item_id: str,
    *,
    hard_delete: bool = False,
) -> dict[str, Any]:
    todo = _get_todo_list(state)
    removed: dict[str, Any] | None = None
    new_items: list[ResearchTodoItem] = []
    for item in todo.items:
        if item.item_id == item_id:
            removed = item.model_dump()
            if not hard_delete:
                item.status = "cancelled"
                item.completed_at = datetime.utcnow().isoformat()
                new_items.append(item)
        else:
            new_items.append(item)
    todo.items = new_items
    todo.version += 1
    return {
        "removed_item": removed,
    }


def update_research_todo_status(
    state: dict[str, Any],
    item_id: str,
    status: str,
) -> dict[str, Any]:
    todo = _get_todo_list(state)
    updated: dict[str, Any] | None = None
    for item in todo.items:
        if item.item_id == item_id:
            item.status = status  # type: ignore[assignment]
            if status in ("done", "cancelled"):
                item.completed_at = datetime.utcnow().isoformat()
            updated = item.model_dump()
            break
    todo.version += 1
    return {
        "updated_item": updated,
    }


def get_next_research_todo(state: dict[str, Any], question_id: str | None = None) -> dict[str, Any]:
    result = list_research_todos(state, status="pending", question_id=question_id, limit=1)
    items = result.get("items") or []
    if len(items) == 0: 
        return {
            "next_item": "No pending research todo items found." if not question_id else f"No pending research todo items found for question_id={question_id}.",
        } 
    return {
        "next_item": items[0] if items else None,
    }
