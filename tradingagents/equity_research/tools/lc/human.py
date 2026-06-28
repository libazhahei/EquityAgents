"""LangChain human-in-the-loop tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import human_tools


@tool
def ask_human(
    question: Annotated[str, "Question for the user"],
    state: Annotated[dict[str, Any] | None, "Optional research state context"] = None,
) -> dict[str, Any]:
    """Ask the user a clarifying question."""
    return human_tools.ask_human(question, state)


@tool
def human_approval(
    action_summary: Annotated[str, "Summary of the action requiring approval"],
    state: Annotated[dict[str, Any] | None, "Optional research state context"] = None,
) -> dict[str, Any]:
    """Request human approval for a high-risk action."""
    return human_tools.human_approval(action_summary, state)


@tool
def human_review_payload(
    state_summary: Annotated[dict[str, Any], "State summary for human review"],
) -> dict[str, Any]:
    """Present current state for human review."""
    return human_tools.human_review_payload(state_summary)


@tool
def human_select_branch(
    branch_options: Annotated[list[dict[str, Any]], "Exploration branch options"],
) -> dict[str, Any]:
    """Let the user select an exploration branch."""
    return human_tools.human_select_branch(branch_options)
