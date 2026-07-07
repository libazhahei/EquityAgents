"""Section planner subgraph node factories."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.section_planner.state import SectionPlannerState
from tradingagents.equity_research.runtime.exploration_graph import ExplorationGraph
from tradingagents.equity_research.runtime.utils.structured_invoke import invoke_structured_with_retry
from tradingagents.equity_research.tasks.section_planner.prompts import (
    build_background_extractor_prompt,
    build_question_tree_prompt,
    pack_background,
)
from tradingagents.equity_research.tasks.section_planner.schemas import (
    BackgroundExtraction,
    SectionPlannerLLMOutput,
    SectionPlannerRequest,
)
from tradingagents.equity_research.tasks.section_planner.template import interpret_section_template
from tradingagents.equity_research.tasks.section_planner.validate import finalize_plan_from_llm_output
from tradingagents.equity_research.templates.report_template import build_grounding_queries
from tradingagents.equity_research.runtime.utils.messages import clear_messages_update
from tradingagents.equity_research.tools.lc.planner import batch_light_grounding_search

BATCH_GROUNDING_TOOL_NAME = "batch_light_grounding_search"


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _to_request(state: SectionPlannerState) -> SectionPlannerRequest:
    return SectionPlannerRequest(
        ticker=state.get("ticker", ""),
        section_id=state.get("section_id", ""),
        section_title=state.get("section_title", ""),
        required_outputs=list(state.get("required_outputs", [])),
        background_reports=dict(state.get("background_reports", {})),
        user_focus=state.get("user_focus"),
        time_horizon=state.get("time_horizon"),
        allowed_tools=list(state.get("allowed_tools", [])),
        extra_context=dict(state.get("extra_context", {})),
        enable_grounding=bool(state.get("enable_grounding", False)),
        section_intent_hint=str(state.get("section_intent_hint", "")),
    )


def grounding_enabled(state: SectionPlannerState) -> bool:
    if not state.get("enable_grounding"):
        return False
    allowed = state.get("allowed_tools", [])
    return "web_search" in allowed


def create_template_interpreter_node(deps: EquityResearchDeps):
    def template_interpreter(state: SectionPlannerState) -> dict[str, Any]:
        section_id = state.get("section_id", "")
        try:
            meta = interpret_section_template(section_id)
        except KeyError as exc:
            errors = list(state.get("errors", []))
            errors.append(str(exc))
            return {"errors": errors}
        updates = {
            "section_title": meta["section_title"],
            "required_outputs": meta["required_outputs"],
            "section_intent_hint": meta["section_intent_hint"],
        }
        updates.update(deps.trace({**state, **updates}, "section_planner_template_interpreter", {
            "section_id": section_id,
        }))
        return updates

    return template_interpreter


def create_background_extractor_node(deps: EquityResearchDeps):
    def background_extractor(state: SectionPlannerState) -> dict[str, Any]:
        req = _to_request(state)
        background = pack_background(req.background_reports)
        errors = list(state.get("errors", []))
        extracted: dict[str, Any] = {}

        if background.strip():
            try:
                prompt = build_background_extractor_prompt(req, background)
                result = invoke_structured_with_retry(
                    deps.quick_llm,
                    BackgroundExtraction,
                    prompt,
                    agent_name="section_planner_background_extractor",
                    max_attempts=_max_retries(deps),
                    fallback=lambda: BackgroundExtraction(),
                )
                extracted = result.model_dump()
            except Exception as exc:
                errors.append(f"background_extractor: {exc}")
                extracted = {"evidence_gaps": ["background extraction failed"]}
        else:
            extracted = {"evidence_gaps": ["no background reports provided"]}

        updates: dict[str, Any] = {"extracted_background": extracted}
        if errors:
            updates["errors"] = errors
        updates.update(deps.trace({**state, **updates}, "section_planner_background_extractor", {
            "gaps": len(extracted.get("evidence_gaps", [])),
        }))
        return updates

    return background_extractor


def create_grounding_dispatch_node(deps: EquityResearchDeps):
    def grounding_dispatch(state: SectionPlannerState) -> dict[str, Any]:
        ticker = state.get("ticker", "")
        section_id = state.get("section_id", "")
        queries = build_grounding_queries(section_id, ticker)
        tool_call_id = f"ground_{uuid.uuid4().hex[:8]}"
        return {
            "grounding_queries": queries,
            "_grounding_batch": {"queries": queries, "tool_call_id": tool_call_id},
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "id": tool_call_id,
                        "name": BATCH_GROUNDING_TOOL_NAME,
                        "args": {"queries": queries},
                    }],
                ),
            ],
        }

    return grounding_dispatch


def create_grounding_tools_node():
    return ToolNode([batch_light_grounding_search])


def _format_grounding_notes(result: dict[str, Any]) -> str:
    parts: list[str] = []
    for snippet in result.get("snippets", []):
        query = snippet.get("query", "")
        lines = snippet.get("results") or []
        parts.append(f"Query: {query}\n" + "\n".join(lines))
        if snippet.get("error"):
            parts.append(f"ERROR: {snippet['error']}")
    for err in result.get("errors", []):
        parts.append(f"ERROR: {err}")
    return "\n\n".join(parts)


def create_grounding_apply_node(deps: EquityResearchDeps):
    def grounding_apply(state: SectionPlannerState) -> dict[str, Any]:
        messages = state.get("messages", [])
        result: dict[str, Any] | None = None
        for message in reversed(messages):
            if isinstance(message, ToolMessage):
                try:
                    result = json.loads(str(message.content))
                except json.JSONDecodeError:
                    result = {"snippets": [], "errors": [str(message.content)[:200]]}
                break

        result = result or {"snippets": [], "api_calls": 0, "errors": []}
        notes = _format_grounding_notes(result)
        api_calls = int(state.get("api_calls", 0)) + int(result.get("api_calls", 0))
        updates: dict[str, Any] = {
            "grounding_notes": notes,
            "api_calls": api_calls,
            **clear_messages_update(),
            "_grounding_batch": None,
        }
        errors = list(state.get("errors", []))
        errors.extend(result.get("errors") or [])
        if errors:
            updates["errors"] = errors
        updates.update(deps.trace({**state, **updates}, "section_planner_grounding_apply", {
            "queries": len(state.get("grounding_queries", [])),
        }))
        return updates

    return grounding_apply


def create_question_tree_generator_node(deps: EquityResearchDeps):
    def question_tree_generator(state: SectionPlannerState) -> dict[str, Any]:
        req = _to_request(state)
        background = pack_background(req.background_reports)
        errors = list(state.get("errors", []))
        llm_data: dict[str, Any] = {}

        try:
            prompt = build_question_tree_prompt(
                req,
                background,
                state.get("extracted_background", {}),
                state.get("grounding_notes", ""),
            )

            def _fallback() -> SectionPlannerLLMOutput:
                return SectionPlannerLLMOutput(
                    root_question=f"What must be researched to complete {req.section_title} for {req.ticker}?",
                    data_quality_flags=["llm_fallback_used"],
                )

            output = invoke_structured_with_retry(
                deps.quick_llm,
                SectionPlannerLLMOutput,
                prompt,
                agent_name="section_planner_question_tree_generator",
                max_attempts=_max_retries(deps),
                fallback=_fallback,
            )
            llm_data = output.model_dump()
        except Exception as exc:
            errors.append(f"question_tree_generator: {exc}")
            llm_data = {
                "root_question": f"What must be researched to complete {req.section_title} for {req.ticker}?",
                "nodes": [],
                "data_quality_flags": ["question_tree_generator_failed"],
            }

        plan = finalize_plan_from_llm_output(llm_data, req)
        updates: dict[str, Any] = {"plan": plan.model_dump()}
        if errors:
            updates["errors"] = errors
        updates.update(deps.trace({**state, **updates}, "section_planner_question_tree_generator", {
            "nodes": len(plan.nodes),
            "flags": len(plan.data_quality_flags),
        }))
        return updates

    return question_tree_generator


def create_coverage_validator_node(deps: EquityResearchDeps):
    def coverage_validator(state: SectionPlannerState) -> dict[str, Any]:
        req = _to_request(state)
        plan_dict = dict(state.get("plan", {}))
        plan = finalize_plan_from_llm_output(plan_dict, req)
        updates = {"plan": plan.model_dump()}
        updates.update(deps.trace({**state, **updates}, "section_planner_coverage_validator", {
            "coverage_outputs": len(plan.coverage_map),
        }))
        return updates

    return coverage_validator


def create_finalize_plan_node(deps: EquityResearchDeps):
    def finalize_plan(state: SectionPlannerState) -> dict[str, Any]:
        req = _to_request(state)
        plan_dict = dict(state.get("plan", {}))
        from tradingagents.equity_research.tasks.section_planner.validate import to_plan

        plan = to_plan(plan_dict) if plan_dict.get("nodes") else finalize_plan_from_llm_output(plan_dict, req)

        graph = ExplorationGraph.from_dict(state.get("exploration_graph"))
        branch_id = f"{req.ticker}_{req.section_id}_planner"
        query_plan = [
            {
                "question_id": node.id,
                "parent_id": node.parent_id,
                "level": node.level,
                "question": node.question,
                "priority": node.priority,
                "required_evidence": node.required_evidence,
                "suggested_sources": node.suggested_sources,
                "expected_output": node.expected_output,
                "downstream_agent": node.downstream_agent,
                "stop_condition_hint": node.stop_condition_hint,
            }
            for node in plan.nodes
        ]
        graph.new_node(
            parent_id=None,
            branch_id=branch_id,
            query_plan=query_plan,
            structured_view_snapshot={
                "type": "section_research_plan",
                "plan": plan.model_dump(),
            },
            coverage_score=1.0 if not plan.data_quality_flags else 0.8,
            routing_decision="ready_for_research_loop",
        )

        updates = {
            "plan": plan.model_dump(),
            "exploration_graph": graph.to_dict(),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "section_planner_finalize", {
            "section_id": req.section_id,
            "node_count": len(plan.nodes),
        }))
        return updates

    return finalize_plan


def grounding_router(state: SectionPlannerState) -> str:
    return "grounding_dispatch" if grounding_enabled(state) else "question_tree_generator"
