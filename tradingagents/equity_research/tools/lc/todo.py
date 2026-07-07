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
    """Return current research todo items from state."""
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
    """Append a research todo item."""
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
    """Remove or cancel a research todo item by item_id."""
    return todo_tools.remove_research_todo(state, item_id)


@tool
def update_research_todo_status(
    state: Annotated[dict[str, Any], InjectedState],
    item_id: Annotated[str, "Todo item id"],
    status: Annotated[str, "New status: pending|in_progress|done|cancelled"],
) -> dict[str, Any]:
    """Update status of a research todo item."""
    return todo_tools.update_research_todo_status(state, item_id, status)


@tool
def get_next_research_todo(
    state: Annotated[dict[str, Any], InjectedState],
) -> dict[str, Any]:
    """Return highest-priority pending research todo item."""
    return todo_tools.get_next_research_todo(state)
