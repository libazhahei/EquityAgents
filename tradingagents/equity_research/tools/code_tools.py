"""Code read/write and sandbox tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tradingagents.dataflows.config import get_config
from tradingagents.equity_research.integrations.e2b_sandbox import E2BSandbox
from tradingagents.equity_research.tools.workspace_utils import get_code_root, resolve_safe_path


def _code_enabled(feature: str) -> bool:
    er = get_config().get("equity_research") or {}
    tools_cfg = er.get("tools", {})
    return bool(tools_cfg.get(feature, False))


def code_reader(path: str) -> dict[str, Any]:
    target = resolve_safe_path(path, get_code_root())
    if not target.is_file():
        return {"path": str(target), "content": "", "error": "not found"}
    return {"path": str(target), "content": target.read_text(encoding="utf-8", errors="replace")}


def code_search(query: str, path: str = ".") -> dict[str, Any]:
    root = resolve_safe_path(path, get_code_root())
    matches = []
    for file in root.rglob("*.py") if root.is_dir() else [root]:
        if not file.is_file():
            continue
        try:
            text = file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for i, line in enumerate(text.splitlines(), 1):
            if query.lower() in line.lower():
                matches.append({"file": str(file), "line": i, "text": line.strip()})
    return {"query": query, "matches": matches[:50]}


def code_writer(path: str, content: str) -> dict[str, Any]:
    if not _code_enabled("code_writer"):
        return {"status": "denied", "reason": "code_writer disabled in config"}
    target = resolve_safe_path(path, get_code_root())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"path": str(target), "status": "written"}


def python_exec_sandbox(code: str) -> dict[str, Any]:
    if not _code_enabled("python_exec_sandbox"):
        return {"status": "denied", "reason": "python_exec_sandbox disabled in config"}
    return E2BSandbox().run_python(code)


def shell_exec_sandbox(command: str) -> dict[str, Any]:
    if not _code_enabled("shell_exec_sandbox"):
        return {"status": "denied", "reason": "shell_exec_sandbox disabled in config"}
    return E2BSandbox().run_shell(command)
