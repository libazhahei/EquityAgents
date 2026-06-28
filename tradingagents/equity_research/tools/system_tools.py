"""System tools: registry lookup and state snapshots."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.tools.tool_catalog import (
    SKILL_DOMAINS,
    all_tool_specs,
    list_tool_categories,
    list_tools_in_category,
)

_SNAPSHOTS: dict[str, dict[str, Any]] = {}


def ls_tools(category: str | None = None, registered: set[str] | None = None) -> dict[str, Any]:
    if not category:
        return {"level": "categories", "categories": list_tool_categories(registered)}
    tools = list_tools_in_category(category, registered)
    if not tools and category not in {c["id"] for c in list_tool_categories()}:
        return {"level": "tools", "category": category, "tools": [], "error": "unknown category"}
    return {"level": "tools", "category": category, "tools": tools}


def tool_registry_lookup(
    task: str = "",
    tags: list[str] | None = None,
    registered: set[str] | None = None,
) -> dict[str, Any]:
    tags = [t.lower() for t in (tags or [])]
    task_tokens = set(task.lower().split())
    ranked: list[tuple[float, dict[str, Any]]] = []
    for spec in all_tool_specs(registered):
        score = 0.0
        text = f"{spec['name']} {spec['description']} {spec.get('category', '')}".lower()
        if tags:
            score += sum(2.0 for t in tags if t in text or t == spec.get("category"))
        if task_tokens:
            score += sum(1.0 for tok in task_tokens if tok in text)
        if score > 0 or (not tags and not task):
            ranked.append((score, spec))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return {
        "task": task,
        "tags": tags,
        "tools": [s for _, s in ranked[:20]],
    }


def ls_skills(skill_registry: Any, domain: str | None = None) -> dict[str, Any]:
    catalog = skill_registry.get_catalog()
    if not domain:
        domains = []
        for dom_id, meta in SKILL_DOMAINS.items():
            tags = {t.lower() for t in meta.get("tags", [])}
            count = sum(1 for e in catalog if tags & {t.lower() for t in e.tags})
            domains.append({
                "id": dom_id,
                "label": meta.get("label", dom_id),
                "description": meta.get("label", ""),
                "skill_count": count,
            })
        return {"level": "domains", "domains": domains}

    meta = SKILL_DOMAINS.get(domain)
    if not meta:
        return {"level": "skills", "domain": domain, "skills": [], "error": "unknown domain"}
    tags = {t.lower() for t in meta.get("tags", [])}
    skills = []
    for entry in catalog:
        if tags & {t.lower() for t in entry.tags}:
            skills.append({
                "name": entry.name,
                "description": entry.description,
                "when_to_use": (entry.when_to_use or "")[:200],
                "tools": entry.tools,
            })
    return {"level": "skills", "domain": domain, "skills": skills}


def skill_registry_lookup(
    skill_registry: Any,
    task: str = "",
    domain: str | None = None,
) -> dict[str, Any]:
    catalog = skill_registry.get_catalog()
    if domain and domain in SKILL_DOMAINS:
        tags = {t.lower() for t in SKILL_DOMAINS[domain].get("tags", [])}
        catalog = [e for e in catalog if tags & {t.lower() for t in e.tags}]
    task_tokens = set(task.lower().split())
    ranked: list[tuple[float, dict[str, Any]]] = []
    for entry in catalog:
        text = f"{entry.name} {entry.description} {entry.when_to_use} {' '.join(entry.tags)}".lower()
        score = sum(1.0 for tok in task_tokens if tok in text) if task_tokens else 1.0
        if score > 0:
            ranked.append((score, {
                "name": entry.name,
                "description": entry.description,
                "when_to_use": entry.when_to_use,
                "tags": entry.tags,
                "tools": entry.tools,
            }))
    ranked.sort(key=lambda x: x[0], reverse=True)
    return {"task": task, "domain": domain, "skills": [s for _, s in ranked[:15]]}


def state_snapshot(state: dict[str, Any], deps: Any | None = None) -> dict[str, Any]:
    snapshot_id = f"snap_{uuid.uuid4().hex[:12]}"
    payload = {
        "snapshot_id": snapshot_id,
        "created_at": datetime.utcnow().isoformat(),
        "ticker": state.get("ticker"),
        "active_objective": state.get("active_objective"),
        "claims_count": len(state.get("claims", [])),
        "evidence_count": len(state.get("evidence_ledger", [])),
    }
    _SNAPSHOTS[snapshot_id] = {**payload, "state_subset": {
        k: state.get(k) for k in ("ticker", "mandate", "active_objective", "research_status") if k in state
    }}
    if deps is not None:
        deps.trace(state, "state_snapshot", payload)
    return {"snapshot_id": snapshot_id, "status": "saved"}
