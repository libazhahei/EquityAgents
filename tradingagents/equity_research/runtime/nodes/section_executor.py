"""Section research executor — ReAct per active step with grouped tool sets."""

from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.search_memory import append_search_record
from tradingagents.equity_research.state.consensus_schemas import SearchRecord
from tradingagents.equity_research.tasks.section_research.schemas import SectionResearchPlan
from tradingagents.equity_research.tasks.section_research.todo_sync import pick_active_task_and_step
from tradingagents.equity_research.tools.tool_sets import (
    build_executor_tool_set_nodes,
    build_tools_for_group,
    route_tool_group_from_state,
    tool_group_node_name,
)


def build_section_executor_tool_set_nodes(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
) -> dict[str, Any]:
    return build_executor_tool_set_nodes(deps, task_profile, prefix="executor_tools")


def section_executor_router(state: dict[str, Any]) -> str:
    messages = state.get("messages", [])
    if not messages:
        return "apply"
    last = messages[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        max_calls = int(state.get("_executor_max_calls", 6))
        step_calls = int(state.get("_executor_step_calls", 0))
        if step_calls >= max_calls:
            return "apply"
        return "tool_router"
    if isinstance(last, ToolMessage):
        max_calls = int(state.get("_executor_max_calls", 6))
        step_calls = int(state.get("_executor_step_calls", 0))
        if step_calls < max_calls:
            return "continue"
    return "apply"


def _merge_tool_state_updates(state: dict[str, Any], content: str) -> dict[str, Any]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    updates: dict[str, Any] = {}
    if "research_todo_list" in data:
        updates["research_todo_list"] = data["research_todo_list"]
    return updates


def _evidence_from_search(content: str, state: dict[str, Any]) -> list[dict]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    items = data.get("items") if isinstance(data, dict) else None
    if not items:
        return []
    active = state.get("active_task") or {}
    qid = active.get("question_id", "general")
    evidence = []
    for item in items:
        ev = item.get("evidence")
        if ev:
            ev = dict(ev)
            ev["question_id"] = qid
            evidence.append(ev)
    return evidence


def _resolve_active_task_step(state: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    from tradingagents.equity_research.tools.todo_tools import get_next_research_todo

    active_task, active_step = pick_active_task_and_step(state)
    if active_task and active_step:
        return active_task, active_step

    next_todo = get_next_research_todo(state)
    item = next_todo.get("next_item")
    if not item:
        return None, None

    plan_raw = state.get("research_plan") or {}
    task_id = item.get("task_id")
    step_id = item.get("step_id")
    if plan_raw and task_id:
        plan = SectionResearchPlan.model_validate(plan_raw)
        for task in plan.tasks:
            if task.task_id != task_id:
                continue
            for step in task.steps:
                if step.step_id == step_id:
                    return task.model_dump(), step.model_dump()
            synthetic_step = {
                "step_id": step_id or f"todo_{item.get('item_id', '')}",
                "order": 1,
                "action": item.get("action") or "search",
                "description": item.get("description") or item.get("title", ""),
                "tool_hints": item.get("tool_hints") or [],
                "expected_output": item.get("description", ""),
                "status": "in_progress",
            }
            return task.model_dump(), synthetic_step

    synthetic_task = {
        "task_id": task_id or f"todo_task_{item.get('item_id', '')}",
        "question_id": item.get("question_id"),
        "objective": item.get("title", ""),
        "status": "in_progress",
    }
    synthetic_step = {
        "step_id": step_id or f"todo_{item.get('item_id', '')}",
        "order": 1,
        "action": item.get("action") or "search",
        "description": item.get("description") or item.get("title", ""),
        "tool_hints": item.get("tool_hints") or [],
        "expected_output": item.get("description", ""),
        "status": "in_progress",
    }
    return synthetic_task, synthetic_step


def create_section_executor_dispatch_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
):
    build_prompt = task_profile.extra_config.get("build_executor_system_prompt")
    max_calls = int(task_profile.extra_config.get("executor_max_tool_calls_per_step", 6))

    def dispatch(state: dict[str, Any]) -> dict[str, Any]:
        active_task, active_step = _resolve_active_task_step(state)
        if not active_task or not active_step:
            return {"messages": [], "_executor_step_calls": 0}

        messages = list(state.get("messages") or [])
        step_calls = int(state.get("_executor_step_calls", 0))

        working_state = {**state, "active_task": active_task, "active_step": active_step}
        tool_group = route_tool_group_from_state(working_state)
        tools = build_tools_for_group(deps, task_profile, tool_group)
        llm = deps.deep_llm.bind_tools(tools)

        if not messages or (messages and isinstance(messages[-1], ToolMessage)):
            system = build_prompt(state) if build_prompt else ""
            group_hint = (
                f"\nActive tool group: {tool_group}. "
                f"Only use tools from this group ({', '.join(t.name for t in tools[:8])})."
            )
            if not messages:
                messages = [
                    SystemMessage(content=(system + group_hint) if system else group_hint.strip()),
                    HumanMessage(content=f"Execute step: {active_step.get('description', '')}"),
                ]
            response = llm.invoke(messages)
            new_calls = step_calls + (1 if isinstance(response, AIMessage) and response.tool_calls else 0)
            return {
                "messages": messages + [response],
                "active_task": active_task,
                "active_step": active_step,
                "_executor_tool_group": tool_group,
                "_executor_tool_node": tool_group_node_name(tool_group),
                "_executor_max_calls": max_calls,
                "_executor_step_calls": new_calls,
            }

        if messages and isinstance(messages[-1], AIMessage):
            return {
                "_executor_tool_group": state.get("_executor_tool_group") or tool_group,
                "_executor_tool_node": state.get("_executor_tool_node")
                or tool_group_node_name(tool_group),
                "_executor_max_calls": max_calls,
            }

        return {}

    return dispatch


def create_section_executor_apply_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    agent_trace = f"{task_profile.task_id}_executor_apply"

    def apply(state: dict[str, Any]) -> dict[str, Any]:
        messages = list(state.get("messages") or [])
        errors = list(state.get("errors", []))
        buffer = list(state.get("evidence_buffer", []))
        pending = list(state.get("pending_evidence", []))
        search_memory = list(state.get("search_memory", []))
        documents = list(state.get("documents", []))
        api_calls = int(state.get("api_calls", 0))
        todo_list = dict(state.get("research_todo_list") or {})
        fact_store = list(state.get("fact_store", []))
        calc_store = list(state.get("calculation_store", []))

        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            content = str(message.content)
            updates = _merge_tool_state_updates(state, content)
            if updates.get("research_todo_list"):
                todo_list = updates["research_todo_list"]
            new_ev = _evidence_from_search(content, state)
            for ev in new_ev:
                eid = ev.get("evidence_id") or f"ev_{uuid.uuid4().hex[:8]}"
                ev["evidence_id"] = eid
                buffer.append(ev)
                pending.append(ev)
                record = ev.get("record")
                if record:
                    search_memory = append_search_record(search_memory, SearchRecord(**record))
                doc_ids = ev.get("doc_ids") or []
                for doc_id in doc_ids:
                    if not any(d.get("doc_id") == doc_id for d in documents):
                        documents.append({"doc_id": doc_id})
            if "api_calls" in content:
                try:
                    parsed = json.loads(content)
                    api_calls += int(parsed.get("api_calls", 0))
                except json.JSONDecodeError:
                    pass

        plan_raw = dict(state.get("research_plan") or {})
        active_task = state.get("active_task") or {}
        active_step = state.get("active_step") or {}
        step_id = active_step.get("step_id")
        task_id = active_task.get("task_id")

        if plan_raw and step_id and task_id:
            plan = SectionResearchPlan.model_validate(plan_raw)
            for task in plan.tasks:
                if task.task_id != task_id:
                    continue
                task.status = "in_progress"
                all_done = True
                for step in task.steps:
                    if step.step_id == step_id:
                        step.status = "done"
                        step.result_summary = "Step completed via executor"
                    if step.status not in ("done", "skipped"):
                        all_done = False
                if all_done:
                    task.status = "done"
            plan_raw = plan.model_dump()
            active_task, active_step = pick_active_task_and_step({**state, "research_plan": plan_raw})

        if todo_list and step_id:
            items = todo_list.get("items") or []
            for item in items:
                if item.get("step_id") == step_id and item.get("status") != "done":
                    item["status"] = "done"
                    break
            todo_list["items"] = items

        result: dict[str, Any] = {
            "messages": [],
            "evidence_buffer": buffer,
            "pending_evidence": pending,
            "search_memory": search_memory,
            "documents": documents,
            "api_calls": api_calls,
            "research_plan": plan_raw,
            "research_todo_list": todo_list,
            "fact_store": fact_store,
            "calculation_store": calc_store,
            "active_task": active_task,
            "active_step": active_step,
            "_executor_step_calls": 0,
            "_executor_tool_node": None,
            "_executor_tool_group": None,
        }
        if errors:
            result["errors"] = errors
        result.update(deps.trace({**state, **result}, agent_trace, {
            "pending_evidence": len(pending),
            "step_id": step_id,
        }))
        return result

    return apply


# Backward-compatible alias for imports expecting a single tools node factory.
def create_section_executor_tools_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    nodes = build_section_executor_tool_set_nodes(deps, task_profile)
    return nodes[tool_group_node_name("retrieval")]
