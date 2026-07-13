"""LangChain findings-cache tools for section research executor."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.prebuilt import InjectedState

from tradingagents.equity_research.tools import findings_cache_tools

_STATE = Annotated[dict[str, Any], InjectedState]


@tool
def findings_cache_write(
    state: _STATE,
    findings: Annotated[
        list[dict[str, Any]] | dict[str, Any],
        "One finding or list of findings with claim/source/period/url/metric/value",
    ],
    replace: Annotated[bool, "If true, replace entire cache instead of appending"] = False,
) -> dict[str, Any]:
    """Persist key research findings to the section findings_cache.json file.

    Use when dialogue context is growing large or before finishing a retrieval step,
    so later steps can recover facts via findings_cache_read without re-fetching.
    Dialogue side is always collapsed to summary \"ok\" (facts live on disk).
    """
    return findings_cache_tools.findings_cache_write(state, findings, replace=replace)


@tool
def findings_cache_read(
    state: _STATE,
    question_id: Annotated[str | None, "Optional filter by question_id"] = None,
    limit: Annotated[int, "Max items to return (most recent)"] = 50,
) -> dict[str, Any]:
    """Read findings previously written to the section findings_cache.json file.

    Returns full items into the dialogue so the model can reuse them. If dialogue
    grows too large, the executor may later compact this payload like other tools.
    """
    return findings_cache_tools.findings_cache_read(
        state, question_id=question_id, limit=limit,
    )
