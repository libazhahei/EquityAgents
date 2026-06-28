"""Artifact writer tools."""

from __future__ import annotations

import json
from typing import Any

from tradingagents.equity_research.tools.workspace_utils import resolve_safe_path


def markdown_writer(content: str, path: str) -> dict[str, Any]:
    target = resolve_safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": str(target), "status": "written", "bytes": len(content.encode())}


def json_writer(data: dict | list, path: str) -> dict[str, Any]:
    target = resolve_safe_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False)
    target.write_text(text, encoding="utf-8")
    return {"path": str(target), "status": "written", "bytes": len(text.encode())}
