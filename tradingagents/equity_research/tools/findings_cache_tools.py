"""Section-scoped findings cache for executor offload."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradingagents.equity_research.tools.workspace_utils import get_document_root


def section_run_dir(ticker: str, section_id: str) -> Path:
    safe_ticker = (ticker or "unknown").strip() or "unknown"
    safe_section = (section_id or "section").strip() or "section"
    return get_document_root() / "section_runs" / safe_ticker / safe_section


def findings_cache_path(ticker: str, section_id: str) -> Path:
    return section_run_dir(ticker, section_id) / "findings_cache.json"


def articles_dir(ticker: str, section_id: str) -> Path:
    return section_run_dir(ticker, section_id) / "articles"


def _load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"items": [], "updated_at": None}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"items": [], "updated_at": None}
    if not isinstance(data, dict):
        return {"items": [], "updated_at": None}
    items = data.get("items")
    if not isinstance(items, list):
        items = []
    return {"items": items, "updated_at": data.get("updated_at")}


def findings_cache_write(
    state: dict[str, Any],
    findings: list[dict[str, Any]] | dict[str, Any],
    *,
    replace: bool = False,
) -> dict[str, Any]:
    """Append (or replace) structured findings in the section cache file."""
    ticker = str(state.get("ticker") or "")
    section_id = str(state.get("section_id") or "")
    path = findings_cache_path(ticker, section_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(findings, dict):
        batch = [findings]
    else:
        batch = [f for f in findings if isinstance(f, dict)]
    existing = _load_cache(path)
    items = [] if replace else list(existing.get("items") or [])
    now = datetime.now(timezone.utc).isoformat()
    for item in batch:
        entry = {
            "question_id": str(item.get("question_id") or (state.get("active_task") or {}).get("question_id") or ""),
            "claim": str(item.get("claim") or item.get("text") or item.get("summary") or ""),
            "source": str(item.get("source") or ""),
            "period": str(item.get("period") or ""),
            "url": str(item.get("url") or ""),
            "metric": str(item.get("metric") or ""),
            "value": item.get("value"),
            "unit": str(item.get("unit") or ""),
            "written_at": now,
        }
        if entry["claim"] or entry["metric"] or entry["url"]:
            items.append(entry)
    payload = {"items": items, "updated_at": now}
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "status": "ok",
        "path": str(path),
        "count": len(items),
        "added": len(batch),
        "summary": "ok",
    }


def findings_cache_read(
    state: dict[str, Any],
    *,
    question_id: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    """Read structured findings from the section cache file."""
    ticker = str(state.get("ticker") or "")
    section_id = str(state.get("section_id") or "")
    path = findings_cache_path(ticker, section_id)
    data = _load_cache(path)
    items = list(data.get("items") or [])
    if question_id:
        qid = str(question_id)
        items = [i for i in items if str(i.get("question_id") or "") == qid]
    if limit > 0:
        items = items[-limit:]
    return {
        "status": "ok",
        "path": str(path),
        "items": items,
        "count": len(items),
        "summary": f"count={len(items)}",
    }


def resolve_section_artifact_dir(state: dict[str, Any]) -> Path:
    """Return (and create) the articles directory for this section run."""
    existing = state.get("section_artifact_dir")
    if existing:
        path = Path(str(existing))
        path.mkdir(parents=True, exist_ok=True)
        return path
    path = articles_dir(str(state.get("ticker") or ""), str(state.get("section_id") or ""))
    path.mkdir(parents=True, exist_ok=True)
    return path
