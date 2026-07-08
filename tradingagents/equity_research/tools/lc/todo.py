"""LangChain tools for research todo list CRUD."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tradingagents.equity_research.tools import todo_tools


@tool
def list_research_todos(
    state: Annotated[dict[str, Any], InjectedState],
    status: Annotated[str | None, "Filter: pending|in_progress|done|cancelled"] = None,
    question_id: Annotated[str | None, "Filter by question id"] = None,
    limit: Annotated[int | None, "Max items to return, max 10"] = None,
) -> dict[str, Any]:
    """
    WHEN: At the start of every execution step, and whenever you need to see what work is queued.
    USE CASES:
    - Overview: call with status="pending" to see all remaining items, sorted by priority.
    - Scope check: call with question_id to see items for a specific question.
    - Audit: call with status="in_progress" to find stuck or orphaned items.

    Return current research todo items from state.
    Optional filters: status, question_id, limit.
    It returns a dict with keys: 
        items (list of todo items), 
        total (total matching items), 
        remaining (remaining items after limit).
    """
    return todo_tools.list_research_todos(
        state, status=status, question_id=question_id, limit=max(10, limit) if limit is not None else 10,
    )


@tool
def add_research_todo(
    state: Annotated[dict[str, Any], InjectedState],
    title: Annotated[str, "Short title for the todo item"],
    description: Annotated[str, "Detailed description or success criteria"] = "",
    question_id: Annotated[str | None, "Related question id"] = None,
    action: Annotated[str | None, "Step action type e.g. search, fetch_primary"] = None,
    priority: Annotated[int, "Priority 0-100"] = 50,
    tool_hints: Annotated[list[str] | None, "Suggested tools"] = None,
) -> dict[str, Any]:
    """Append a research todo item.
    WHEN: During execution, if you discover work that was not in the original plan.
    USE CASES:
    - A search reveals a follow-up question that needs separate research.
    - Data for a metric is missing; create a fallback-proxy research item.
    - A contradiction is found that requires a dedicated verification task.
    HOW: Set priority (0-100, higher = more urgent), action (e.g. "search", "fetch_primary",
    "extract"), and tool_hints (suggested tools). Always include question_id to link to a question.

    It returns a dict with keys:
        added_item (the new todo item)
    """
    return todo_tools.add_research_todo(
        state,
        title=title,
        description=description,
        question_id=question_id,
        action=action,
        priority=priority,
        tool_hints=tool_hints,
    )


@tool
def remove_research_todo(
    state: Annotated[dict[str, Any], InjectedState],
    item_id: Annotated[str, "Todo item id to remove or cancel"],
) -> dict[str, Any]:
    """Remove or cancel a research todo item by item_id.
    WHEN: An item is provably obsolete (e.g. the question was removed from scope, or the data
    source is permanently unavailable and no fallback exists).
    NOTE: This performs a soft-cancel (status → cancelled) by default. Prefer
    update_research_todo_status(item_id, "cancelled") for traceability. Only use remove_research_todo
    when you explicitly need the item removed from the list entirely

    It returns a dict with keys:
        removed_item (the removed todo item)
  """
    return todo_tools.remove_research_todo(state, item_id)


@tool
def update_research_todo_status(
    state: Annotated[dict[str, Any], InjectedState],
    item_id: Annotated[str, "Todo item id"],
    status: Annotated[str, "New status: pending|in_progress|done|cancelled"],
) -> dict[str, Any]:
    """Update status of a research todo item.

    WHEN: When progress changes for an item (starting work, completing, or cancelling).
    USE CASES:
    - Start work: set status="in_progress" when an agent begins a task.
    - Complete work: set status="done" when success criteria are met.
    - Cancel: set status="cancelled" when the item is no longer relevant.

    It returns a dict with keys:
        updated_item (the todo item after status update)
    """
    return todo_tools.update_research_todo_status(state, item_id, status)


@tool
def get_next_research_todo(
    state: Annotated[dict[str, Any], InjectedState],
    question_id: Annotated[str | None, "Optional filter by question id"] = None,
) -> dict[str, Any]:
    """
    WHEN: After finishing the current item, or when you need to decide what to work on next.
  USE CASES:
  - Picking the next task: returns the single highest-priority pending item.
  - Avoids manual sorting — the queue is pre-sorted by priority.
  Use this instead of list_research_todos when you only need the next item.

    It returns a dict with keys:
        next_item (the highest-priority pending todo item, or None if none exist)
  """
    return todo_tools.get_next_research_todo(state, question_id=question_id)
