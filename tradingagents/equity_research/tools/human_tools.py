"""Human-in-the-loop tools."""

from __future__ import annotations

from typing import Any

from tradingagents.dataflows.config import get_config


def _human_mode() -> str:
    er = get_config().get("equity_research") or {}
    return er.get("human_tools_mode", "stub")


def ask_human(question: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    if _human_mode() == "stub":
        return {"status": "stub", "question": question, "answer": "[awaiting human input]"}
    return {"status": "interrupt", "type": "ask_human", "question": question}


def human_approval(action_summary: str, state: dict[str, Any] | None = None) -> dict[str, Any]:
    if _human_mode() == "stub":
        return {"status": "stub", "approved": True, "action_summary": action_summary}
    return {"status": "interrupt", "type": "human_approval", "action_summary": action_summary}


def human_review_payload(state_summary: dict[str, Any]) -> dict[str, Any]:
    if _human_mode() == "stub":
        return {"status": "stub", "review_payload": state_summary}
    return {"status": "interrupt", "type": "human_review", "payload": state_summary}


def human_select_branch(branch_options: list[dict[str, Any]]) -> dict[str, Any]:
    if _human_mode() == "stub":
        selected = branch_options[0] if branch_options else {}
        return {"status": "stub", "selected": selected}
    return {"status": "interrupt", "type": "human_select_branch", "options": branch_options}
