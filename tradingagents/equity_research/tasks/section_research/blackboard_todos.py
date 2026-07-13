"""Materialize session-blackboard gaps/contradictions into research todos."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.memory.similarity import text_similarity
from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchTodoItem,
    ResearchTodoList,
)
from tradingagents.equity_research.tasks.section_research.todo_sync import (
    pick_active_task_and_step,
)

_DEFAULT_MAX = 3
_DEDUP_SIM = 0.85
_FILING_RE = re.compile(
    r"\b(10-[kq]|8-k|20-f|sec\b|filing|filings|edgar|10k|10q)\b",
    re.I,
)
_MATERIALIZE_TYPES = frozenset({"methodology", "contradiction"})


def blackboard_todo_materialize_enabled(config: dict[str, Any] | None) -> bool:
    """Default True — structured BB→todo consumption for section research."""
    if not isinstance(config, dict):
        return True
    er = config.get("equity_research")
    if not isinstance(er, dict):
        return True
    return bool(er.get("blackboard_todo_materialize", True))


def _skip_verify_enabled(config: dict[str, Any] | None) -> bool:
    if not isinstance(config, dict):
        return False
    er = config.get("equity_research")
    if not isinstance(er, dict):
        return False
    return bool(er.get("skip_verify", False))


def _new_item_id() -> str:
    return f"todo_{uuid.uuid4().hex[:8]}"


def _plan_has_runnable_step(state: dict[str, Any]) -> bool:
    task, step = pick_active_task_and_step(state)
    return bool(task and step)


def _todo_action_for_entry(entry: dict[str, Any], *, skip_verify: bool) -> str:
    entry_type = str(entry.get("entry_type") or "")
    content = str(entry.get("content") or "")
    if entry_type == "contradiction":
        return "search" if skip_verify else "verify"
    if _FILING_RE.search(content):
        return "fetch_primary"
    return "search"


def _priority_for_entry(entry: dict[str, Any]) -> int:
    return 90 if str(entry.get("entry_type") or "") == "contradiction" else 80


def _already_materialized(todo: ResearchTodoList, entry: dict[str, Any]) -> bool:
    entry_id = str(entry.get("entry_id") or "")
    content = str(entry.get("content") or "").strip()
    for item in todo.items:
        if item.status not in ("pending", "in_progress"):
            continue
        if entry_id and getattr(item, "blackboard_entry_id", None) == entry_id:
            return True
        blob = f"{item.title} {item.description}".strip()
        if content and blob and text_similarity(content, blob) >= _DEDUP_SIM:
            return True
    return False


def materialize_blackboard_todos(
    state: dict[str, Any],
    blackboard_entries: list[dict[str, Any]] | None,
    *,
    config: dict[str, Any] | None = None,
    max_items: int = _DEFAULT_MAX,
) -> ResearchTodoList | None:
    """Append BB methodology/contradiction notes as todos when the plan is idle.

    Returns an updated ``ResearchTodoList`` when items were added; otherwise None.
    """
    if not blackboard_todo_materialize_enabled(config):
        return None
    if max_items <= 0 or not blackboard_entries:
        return None
    if _plan_has_runnable_step(state):
        return None

    raw = state.get("research_todo_list") or {}
    section_id = str(state.get("section_id") or raw.get("section_id") or "")
    if raw:
        todo = ResearchTodoList.model_validate(raw)
    else:
        todo = ResearchTodoList(list_id=f"todo_{section_id}", section_id=section_id)

    skip_verify = _skip_verify_enabled(config)
    candidates = [
        e
        for e in blackboard_entries
        if isinstance(e, dict) and str(e.get("entry_type") or "") in _MATERIALIZE_TYPES
    ]
    # Prefer contradictions, then higher confidence, then newer iteration.
    candidates.sort(
        key=lambda e: (
            0 if str(e.get("entry_type") or "") == "contradiction" else 1,
            -float(e.get("confidence") or 0.0),
            -int(e.get("created_at_iteration") or 0),
        )
    )

    added: list[ResearchTodoItem] = []
    for entry in candidates:
        if len(added) >= max_items:
            break
        if _already_materialized(todo, entry):
            continue
        content = str(entry.get("content") or "").strip()
        if len(content) < 10:
            continue
        title = content[:120]
        action = _todo_action_for_entry(entry, skip_verify=skip_verify)
        tool_hints: list[str] = []
        if action == "fetch_primary":
            tool_hints = ["filings_search", "filing_reader", "financial_statement_fetch"]
        elif action == "verify":
            tool_hints = ["citation_checker", "claim_evidence_checker", "search_evidence"]
        else:
            tool_hints = ["web_search", "filings_search", "memory_retrieve"]

        item = ResearchTodoItem(
            item_id=_new_item_id(),
            title=title,
            description=content,
            question_id=entry.get("question_id"),
            action=action,
            priority=_priority_for_entry(entry),
            status="pending",
            source="reflector",
            tool_hints=tool_hints,
            blackboard_entry_id=str(entry.get("entry_id") or "") or None,
            created_at=datetime.utcnow().isoformat(),
        )
        todo.items.append(item)
        added.append(item)

    if not added:
        return None
    todo.version += 1
    return todo
