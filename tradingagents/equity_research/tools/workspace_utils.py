"""Workspace path helpers for file/code tools."""

from __future__ import annotations

from pathlib import Path

from tradingagents.dataflows.config import get_config


def get_document_root() -> Path:
    cfg = get_config()
    er = cfg.get("equity_research") or {}
    root = er.get("document_root") or cfg.get("equity_research_results_dir") or cfg.get("results_dir", ".")
    return Path(root).resolve()


def get_code_root() -> Path:
    cfg = get_config()
    er = cfg.get("equity_research") or {}
    root = er.get("code_root") or cfg.get("project_dir", ".")
    return Path(root).resolve()


def resolve_safe_path(file_path: str, root: Path | None = None) -> Path:
    root = (root or get_document_root()).resolve()
    target = (root / file_path).resolve() if not Path(file_path).is_absolute() else Path(file_path).resolve()
    if not str(target).startswith(str(root)):
        raise ValueError(f"Path escapes workspace root: {file_path}")
    return target
