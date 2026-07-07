"""State for section question tree planner subgraph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import add_messages

from tradingagents.equity_research.tasks.section_planner.schemas import SectionPlannerRequest


class SectionPlannerState(TypedDict, total=False):
    ticker: str
    section_id: str
    section_title: str
    required_outputs: list[str]
    background_reports: dict[str, str]
    user_focus: str | None
    time_horizon: str | None
    allowed_tools: list[str]
    extra_context: dict[str, Any]
    enable_grounding: bool
    section_intent_hint: str

    extracted_background: dict[str, Any]
    grounding_queries: list[str]
    grounding_notes: str
    plan: dict[str, Any]
    exploration_graph: dict[str, Any]

    messages: Annotated[list[Any], add_messages]
    _grounding_batch: dict[str, Any] | None
    api_calls: int
    errors: list[str]
    research_traces: list[dict]


def empty_section_planner_state(req: SectionPlannerRequest | dict[str, Any]) -> SectionPlannerState:
    if isinstance(req, SectionPlannerRequest):
        data = req.model_dump()
    else:
        data = dict(req)
    return SectionPlannerState(
        ticker=data.get("ticker", ""),
        section_id=data.get("section_id", ""),
        section_title=data.get("section_title", ""),
        required_outputs=list(data.get("required_outputs", [])),
        background_reports=dict(data.get("background_reports", {})),
        user_focus=data.get("user_focus"),
        time_horizon=data.get("time_horizon"),
        allowed_tools=list(data.get("allowed_tools", [])),
        extra_context=dict(data.get("extra_context", {})),
        enable_grounding=bool(data.get("enable_grounding", False)),
        section_intent_hint=str(data.get("section_intent_hint", "")),
        extracted_background={},
        grounding_queries=[],
        grounding_notes="",
        plan={},
        exploration_graph={"nodes": {}, "branch_roots": {}},
        messages=[],
        _grounding_batch=None,
        api_calls=int(data.get("api_calls", 0)),
        errors=list(data.get("errors", [])),
        research_traces=list(data.get("research_traces", [])),
    )


def build_section_planner_request(
    state: dict[str, Any],
    section_id: str,
    background_reports: dict[str, str],
    *,
    enable_grounding: bool = False,
) -> SectionPlannerRequest:
    from tradingagents.equity_research.tasks.section_planner.template import interpret_section_template

    meta = interpret_section_template(section_id)
    allowed_tools = ["web_search"] if enable_grounding else []
    return SectionPlannerRequest(
        ticker=str(state.get("ticker", "")),
        section_id=section_id,
        section_title=meta["section_title"],
        required_outputs=meta["required_outputs"],
        background_reports=background_reports,
        user_focus=state.get("user_focus"),
        time_horizon=state.get("time_horizon") or state.get("mandate", {}).get("time_horizon"),
        allowed_tools=allowed_tools,
        extra_context={
            "sector": state.get("sector", ""),
            "industry": state.get("industry", ""),
            "report_type": state.get("report_type", ""),
        },
        enable_grounding=enable_grounding,
        section_intent_hint=meta["section_intent_hint"],
    )
