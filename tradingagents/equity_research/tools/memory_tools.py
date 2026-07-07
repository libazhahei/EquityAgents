"""Extended memory tools."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.memory.retrieval import build_memory_context
from tradingagents.equity_research.tools import evidence_memory


def memory_retrieve(
    state: dict[str, Any],
    query: str = "",
    filters: dict[str, Any] | None = None,
    *,
    deps: Any = None,
    **_: Any,
) -> dict[str, Any]:
    filters = dict(filters or {})
    if query and "priority_questions" not in filters:
        plan = {"priority_questions": [query]}
    else:
        plan = {"priority_questions": filters.pop("priority_questions", [])} if filters else {}
    if query and not plan.get("priority_questions"):
        plan = {"priority_questions": [query]}
    parent_nodes = filters.pop("parent_nodes", [])
    return build_memory_context(
        state,
        parent_nodes=parent_nodes,
        plan=plan,
        filters=filters or None,
        deps=deps,
    )


def memory_write(state: dict[str, Any], record: dict[str, Any], *, deps: Any = None) -> dict[str, Any]:
    record_type = record.get("type", "evidence")
    created_by = record.get("created_by", "memory_write")
    if record_type == "evidence":
        return evidence_memory.store_evidence(
            state,
            record.get("payload", record),
            deps=deps,
            created_by=created_by,
        )
    if record_type == "claim":
        return evidence_memory.store_claim(
            state,
            record.get("payload", record),
            deps=deps,
            created_by=created_by,
        )
    if record_type == "assumption":
        return evidence_memory.store_assumption(
            state,
            record.get("payload", record),
            deps=deps,
            created_by=created_by,
        )
    if record_type in {"reflection", "action"}:
        reflections = list(state.get("memory_reflections", []))
        entry = {
            "id": f"mem_{uuid.uuid4().hex[:8]}",
            "type": record_type,
            "content": record.get("content", record),
            "created_at": datetime.utcnow().isoformat(),
            "created_by": created_by,
        }
        reflections.append(entry)
        return {"memory_reflections": reflections, "memory_id": entry["id"]}
    return {"error": f"unknown record type: {record_type}"}
