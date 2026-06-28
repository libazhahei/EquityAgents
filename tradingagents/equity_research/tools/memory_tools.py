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
    **_: Any,
) -> dict[str, Any]:
    plan = {"priority_questions": [query]} if query else {}
    ctx = build_memory_context(state, parent_nodes=filters.get("parent_nodes", []) if filters else [], plan=plan)
    return ctx


def memory_write(state: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    record_type = record.get("type", "evidence")
    if record_type == "evidence":
        return evidence_memory.store_evidence(state, record.get("payload", record))
    if record_type == "claim":
        return evidence_memory.store_claim(state, record.get("payload", record))
    if record_type == "assumption":
        return evidence_memory.store_assumption(state, record.get("payload", record))
    if record_type in {"reflection", "action"}:
        reflections = list(state.get("memory_reflections", []))
        entry = {
            "id": f"mem_{uuid.uuid4().hex[:8]}",
            "type": record_type,
            "content": record.get("content", record),
            "created_at": datetime.utcnow().isoformat(),
        }
        reflections.append(entry)
        return {"memory_reflections": reflections, "memory_id": entry["id"]}
    return {"error": f"unknown record type: {record_type}"}
