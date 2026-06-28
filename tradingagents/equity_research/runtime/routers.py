"""Routing for generic research subgraphs."""

from __future__ import annotations

from langchain_core.messages import AIMessage
from typing import Any


def skill_selector_router(state: dict[str, Any]) -> str:
    messages = state.get("messages") or []
    if not messages:
        return "apply"
    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "apply"


def coverage_reflector_router(state: dict[str, Any]) -> str:
    report = state.get("coverage_report") or {}
    if report.get("routing_decision", "exit") == "exit":
        return "exit"
    if state.get("query_queue"):
        return "run_existing_queue"
    return "plan_more"


def loop_planner_router(state: dict[str, Any]) -> str:
    if state.get("query_queue"):
        return "run"
    return "exit"


# Backward-compatible alias
gap_query_planner_router = loop_planner_router


def human_review_router(state: dict[str, Any]) -> str:
    if state.get("_pending_human_followup"):
        return "replan"
    return "done"
