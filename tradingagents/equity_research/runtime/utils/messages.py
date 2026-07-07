"""Helpers for LangGraph message state updates."""

from __future__ import annotations

from typing import Any

from langchain_core.messages import RemoveMessage
from langgraph.graph import add_messages
from langgraph.graph.message import REMOVE_ALL_MESSAGES


def clear_messages_update() -> dict:
    """Return a state update that clears the messages channel (requires add_messages reducer)."""
    return {"messages": [RemoveMessage(id=REMOVE_ALL_MESSAGES)]}


def materialize_messages_update(
    prior: list[Any] | None,
    update: list[Any] | None,
) -> list[Any]:
    """Apply an add_messages-style update outside of a compiled graph."""
    return list(add_messages(prior or [], update or []))
