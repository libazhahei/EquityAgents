"""Section research executor — ReAct per active step with grouped tool sets."""

from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.executor_context import format_executor_messages
from tradingagents.equity_research.runtime.utils.messages import clear_messages_update
from tradingagents.equity_research.runtime.utils.llm_invoke import invoke_llm_with_retry
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.runtime.utils.search_memory import append_search_record
from tradingagents.equity_research.state.consensus_schemas import SearchRecord
from tradingagents.equity_research.tasks.section_research.schemas import SectionResearchPlan
from tradingagents.equity_research.tasks.section_research.todo_sync import pick_active_task_and_step
from tradingagents.equity_research.tools.tool_sets import (
    ACTION_TO_GROUP,
    build_executor_tool_set_nodes,
    build_tools_for_group,
    route_tool_group_from_state,
    tool_group_node_name,
)

_SYNTHESIZER_HANDOFF_ACTIONS = frozenset({"synthesize"})


def _is_synthesizer_handoff(step: dict[str, Any] | None) -> bool:
    if not step:
        return False
    return (step.get("action") or "").lower() in _SYNTHESIZER_HANDOFF_ACTIONS


def _question_id_from_state(state: dict[str, Any]) -> str:
    active = state.get("active_task") or {}
    return str(active.get("question_id") or "general")


def _parse_tool_content(content: str | Any) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    try:
        data = json.loads(str(content))
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def _make_evidence(
    qid: str,
    snippet: str,
    *,
    source: str = "",
    url: str = "",
    evidence_id: str | None = None,
    doc_id: str | None = None,
    record: dict | None = None,
) -> dict[str, Any]:
    ev: dict[str, Any] = {
        "evidence_id": evidence_id or f"ev_{uuid.uuid4().hex[:8]}",
        "question_id": qid,
        "snippet": snippet,
        "content": snippet,
        "source": source,
        "url": url,
    }
    if doc_id:
        ev["doc_id"] = doc_id
        ev["doc_ids"] = [doc_id]
    if record:
        ev["record"] = record
    return ev


def _evidence_from_batch_items(data: dict[str, Any], qid: str) -> list[dict]:
    evidence: list[dict] = []
    for item in data.get("items") or []:
        if not isinstance(item, dict):
            continue
        ev = item.get("evidence")
        if ev:
            ev = dict(ev)
            ev["question_id"] = qid
            evidence.append(ev)
    return evidence


def _evidence_from_search_results(data: dict[str, Any], qid: str) -> list[dict]:
    evidence: list[dict] = []
    for item in data.get("results") or []:
        if not isinstance(item, dict):
            continue
        snippet = str(
            item.get("content") or item.get("snippet") or item.get("text") or item.get("title") or ""
        )
        if not snippet:
            continue
        evidence.append(_make_evidence(
            qid,
            snippet,
            source=str(item.get("title") or item.get("source") or ""),
            url=str(item.get("url") or ""),
            doc_id=str(item["doc_id"]) if item.get("doc_id") else None,
        ))
    return evidence


def _evidence_from_grounding_snippets(data: dict[str, Any], qid: str) -> list[dict]:
    evidence: list[dict] = []
    for block in data.get("snippets") or []:
        if not isinstance(block, dict):
            continue
        query = str(block.get("query") or "")
        for line in block.get("results") or []:
            text = str(line)
            if text.strip():
                evidence.append(_make_evidence(qid, text, source=query or "web_search"))
    return evidence


def _evidence_from_text_fields(data: dict[str, Any], qid: str) -> list[dict]:
    evidence: list[dict] = []
    for key in ("content", "text", "section_text", "excerpt"):
        text = data.get(key)
        if isinstance(text, str) and text.strip():
            evidence.append(_make_evidence(
                qid,
                text,
                source=str(data.get("source") or data.get("section") or key),
                url=str(data.get("url") or data.get("filing_url") or ""),
            ))
            break
    for chunk in data.get("chunks") or []:
        if isinstance(chunk, dict):
            text = str(chunk.get("content") or chunk.get("text") or "")
            if text.strip():
                evidence.append(_make_evidence(
                    qid,
                    text,
                    source=str(chunk.get("source") or data.get("section") or "filing"),
                ))
        elif isinstance(chunk, str) and text.strip():
            evidence.append(_make_evidence(qid, chunk, source="filing"))
    return evidence


def _evidence_from_memory_tool(data: dict[str, Any], qid: str) -> list[dict]:
    evidence: list[dict] = []
    fragments = data.get("evidence_fragments") or []
    if fragments:
        latest = fragments[-1] if isinstance(fragments, list) else fragments
        if isinstance(latest, dict):
            snippet = str(latest.get("quote") or latest.get("snippet") or latest.get("content") or "")
            evidence.append(_make_evidence(
                qid,
                snippet,
                source=str(latest.get("source") or "store_evidence"),
                evidence_id=str(latest.get("fragment_id") or latest.get("evidence_id") or "") or None,
                doc_id=str(latest.get("doc_id")) if latest.get("doc_id") else None,
            ))
    eid = data.get("evidence_id")
    if eid and not evidence:
        for entry in data.get("evidence_ledger") or []:
            if isinstance(entry, dict) and entry.get("evidence_id") == eid:
                snippet = str(entry.get("quote") or entry.get("snippet") or entry.get("content") or "")
                evidence.append(_make_evidence(
                    qid,
                    snippet,
                    source=str(entry.get("source") or "evidence_ledger"),
                    evidence_id=str(eid),
                ))
                break
    return evidence



def _evidence_from_filing_hits(data: dict[str, Any], qid: str) -> list[dict]:
    """Extract evidence from filings_search results: data['hits'] with 'chunk_text'."""
    evidence: list[dict] = []
    hits = data.get("hits") or []
    if not isinstance(hits, list):
        return evidence
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        text = str(hit.get("chunk_text") or "")
        if not text:
            continue
        source_parts = []
        form = hit.get("form")
        if form:
            source_parts.append(str(form))
        section = hit.get("subsection_title") or hit.get("section")
        if section:
            source_parts.append(str(section))
        evidence.append(_make_evidence(
            qid,
            text,
            source=":".join(source_parts) if source_parts else "filing",
            url=str(hit.get("url") or ""),
            record={
                "query": str(data.get("keywords", "")),
                "source": f"filing:{form or 'unknown'}:{section or 'unknown'}",
                "url": str(hit.get("url") or ""),
            },
        ))
    return evidence


def _evidence_from_transcript_results(data: dict[str, Any], qid: str) -> list[dict]:
    """Extract evidence from transcript_search results: data['transcripts'] or data['earnings_calls']."""
    evidence: list[dict] = []
    transcripts = data.get("transcripts") or data.get("earnings_calls") or []
    if not isinstance(transcripts, list):
        return evidence
    for entry in transcripts:
        if not isinstance(entry, dict):
            continue
        text = str(entry.get("content") or entry.get("text") or entry.get("transcript") or "")
        if not text:
            continue
        quarter = entry.get("quarter") or entry.get("date") or ""
        evidence.append(_make_evidence(
            qid,
            text[:2000],
            source=f"transcript:{quarter}" if quarter else "transcript",
            url=str(entry.get("url") or ""),
        ))
    return evidence


def _evidence_from_financial_data(data: dict[str, Any], qid: str) -> list[dict]:
    """Extract evidence from financial_statement_fetch results."""
    evidence: list[dict] = []
    statement_keys = ("income_statement", "balance_sheet", "cash_flow", "cash_flow_statement")
    found_any = False
    for sk in statement_keys:
        statement = data.get(sk)
        if not isinstance(statement, dict):
            continue
        found_any = True
        lines = [f"{sk}:"]
        for period, values in statement.items():
            if isinstance(values, dict):
                formatted = {k: v for k, v in values.items() if v is not None}
                if formatted:
                    lines.append(f"  {period}: {formatted}")
            elif values is not None:
                lines.append(f"  {period}: {values}")
        if len(lines) > 1:
            evidence.append(_make_evidence(
                qid,
                "\n".join(lines),
                source=f"financial_statement:{sk}",
            ))
    return evidence


def _ledger_updates_from_tool(data: dict[str, Any]) -> dict[str, Any]:
    updates: dict[str, Any] = {}
    for key in ("evidence_ledger", "evidence_fragments", "claim_ledger", "assumption_ledger"):
        if key in data:
            updates[key] = data[key]
    return updates


def _calculation_from_tool(data: dict[str, Any], qid: str) -> dict[str, Any] | None:
    if "result" not in data and "expression" not in data:
        return None
    return {
        "question_id": qid,
        "expression": str(data.get("expression", "")),
        "result": data.get("result"),
        "metric": str(data.get("metric") or data.get("expression", "calculation")),
    }


def _evidence_from_tool_data(data: dict[str, Any], state: dict[str, Any]) -> tuple[list[dict], dict[str, Any]]:
    qid = _question_id_from_state(state)
    evidence: list[dict] = []
    state_updates: dict[str, Any] = {}

    evidence.extend(_evidence_from_batch_items(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_search_results(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_filing_hits(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_transcript_results(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_financial_data(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_grounding_snippets(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_text_fields(data, qid))
    if not evidence:
        evidence.extend(_evidence_from_memory_tool(data, qid))

    state_updates.update(_ledger_updates_from_tool(data))
    if "research_todo_list" in data:
        state_updates["research_todo_list"] = data["research_todo_list"]

    calc = _calculation_from_tool(data, qid)
    if calc:
        state_updates.setdefault("_calculations_added", []).append(calc)

    return evidence, state_updates


def _normalize_tool_messages_to_evidence(
    messages: list,
    state: dict[str, Any],
) -> tuple[list[dict], dict[str, Any]]:
    all_evidence: list[dict] = []
    merged_updates: dict[str, Any] = {}
    calculations: list[dict] = []

    for message in messages:
        if not isinstance(message, ToolMessage):
            continue
        data = _parse_tool_content(message.content)
        if not data:
            continue
        new_ev, updates = _evidence_from_tool_data(data, state)
        all_evidence.extend(new_ev)
        calcs = updates.pop("_calculations_added", [])
        calculations.extend(calcs)
        for key, value in updates.items():
            if key in ("evidence_ledger", "evidence_fragments") and key in merged_updates:
                existing = merged_updates[key]
                if isinstance(existing, list) and isinstance(value, list):
                    merged_updates[key] = existing + value
                else:
                    merged_updates[key] = value
            else:
                merged_updates[key] = value

    if calculations:
        merged_updates["_calculations_added"] = calculations
    return all_evidence, merged_updates


def build_section_executor_tool_set_nodes(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
) -> dict[str, Any]:
    return build_executor_tool_set_nodes(deps, task_profile, prefix="executor_tools")


def section_executor_router(state: dict[str, Any]) -> str:
    active_task, active_step = pick_active_task_and_step(state)
    if not active_task or not active_step:
        return "apply"

    if _is_synthesizer_handoff(active_step):
        return "apply"

    messages = state.get("messages", [])
    if not messages:
        return "apply"

    last = messages[-1]
    max_calls = int(state.get("_executor_max_calls", 6))
    step_calls = int(state.get("_executor_step_calls", 0))

    if isinstance(last, AIMessage) and last.tool_calls:
        if step_calls >= max_calls:
            return "apply"
        # Re-route based on actual tool calls (allows group switching)
        group = route_tool_group_from_state(state)
        return tool_group_node_name(group)

    if isinstance(last, ToolMessage):
        if step_calls < max_calls:
            return "continue"
    return "apply"



def _doc_ids_from_tool(content: str) -> list[str]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, dict):
        return []
    doc_ids = [str(doc_id) for doc_id in data.get("doc_ids") or [] if doc_id]
    for item in data.get("results") or []:
        if isinstance(item, dict) and item.get("doc_id"):
            doc_ids.append(str(item["doc_id"]))
    return list(dict.fromkeys(doc_ids))



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
            return {**clear_messages_update(), "_executor_step_calls": 0}

        if _is_synthesizer_handoff(active_step):
            return {
                **clear_messages_update(),
                "active_task": active_task,
                "active_step": active_step,
                "_executor_step_calls": 0,
            }

        messages = list(state.get("messages") or [])
        step_calls = int(state.get("_executor_step_calls", 0))

        working_state = {**state, "active_task": active_task, "active_step": active_step}
        
        # PRIMARY: use step action for group selection
        step_action = (active_step.get("action") or "").lower()
        tool_group = ACTION_TO_GROUP.get(step_action, None)
        if tool_group is None:
            # FALLBACK: use state-based routing (tool calls, hints)
            tool_group = route_tool_group_from_state(working_state)
        
        tools = build_tools_for_group(deps, task_profile, tool_group)
        llm = resolve_research_llm(deps, "deep").bind_tools(tools)
        if not messages or isinstance(messages[-1], ToolMessage):
            system = build_prompt(state) if build_prompt else ""
            
            # Build group hint with action-specific guidance
            group_hint = (
                f"\nActive step action: {step_action}. "
                f"Tool group: {tool_group}. "
                f"Available tools: {', '.join(t.name for t in tools)}."
            )
            # Add action-specific guidance
            if step_action == "orient":
                group_hint += "\nGuidance: Start with memory_retrieve to check prior research, then list_research_todos."
            elif step_action == "fetch_primary":
                group_hint += "\nGuidance: Prefer filings_search with SEC-style queries. Use financial_statement_fetch for structured data."
            elif step_action == "search":
                group_hint += "\nGuidance: Use web_search for news, transcript_search for earnings calls."
            elif step_action == "verify":
                group_hint += "\nGuidance: Use citation_checker and claim_evidence_checker to validate evidence chain."
            
            human_msg = f"Execute step: {active_step.get('description', '')}, expected output: {active_step.get('expected_output', '')}\n"
            human_msg += f"Current active task: {active_task.get('objective', '')} for question id {active_task.get('question_id', '')} and task ID: {active_task.get('task_id', '')}\n"
            if not messages:
                invoke_messages = [
                    SystemMessage(content=(system + group_hint) if system else group_hint.strip()),
                    HumanMessage(content=human_msg),
                ]
            else:
                invoke_messages = messages
            response = invoke_llm_with_retry(
                llm,
                invoke_messages,
                deps=deps,
                agent_name="section_executor",
            )
            new_calls = step_calls + (1 if isinstance(response, AIMessage) and response.tool_calls else 0)
            outbound = invoke_messages + [response] if not messages else [response]
            return {
                "messages": outbound,
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
        pending_before = len(pending)
        search_memory = list(state.get("search_memory", []))
        documents = list(state.get("documents", []))
        api_calls = int(state.get("api_calls", 0))
        todo_list = dict(state.get("research_todo_list") or {})
        fact_store = list(state.get("fact_store", []))
        calc_store = list(state.get("calculation_store", []))
        evidence_ledger = list(state.get("evidence_ledger", []))
        evidence_fragments = list(state.get("evidence_fragments", []))

        new_evidence, tool_updates = _normalize_tool_messages_to_evidence(messages, state)
        if tool_updates.get("research_todo_list"):
            todo_list = tool_updates["research_todo_list"]
        if tool_updates.get("evidence_ledger"):
            evidence_ledger.extend(tool_updates["evidence_ledger"])
        if tool_updates.get("evidence_fragments"):
            evidence_fragments.extend(tool_updates["evidence_fragments"])
        for calc in tool_updates.get("_calculations_added") or []:
            calc_store.append(calc)

        for ev in new_evidence:
            eid = ev.get("evidence_id") or f"ev_{uuid.uuid4().hex[:8]}"
            ev["evidence_id"] = eid
            buffer.append(ev)
            pending.append(ev)
            snippet = str(ev.get("snippet") or ev.get("content") or "")
            if snippet:
                fact_store.append({
                    "question_id": ev.get("question_id"),
                    "evidence_id": eid,
                    "text": snippet,
                    "source": ev.get("source", ""),
                })
            record = ev.get("record")
            if record:
                search_memory = append_search_record(search_memory, SearchRecord(**record))
            doc_ids = ev.get("doc_ids") or []
            if ev.get("doc_id"):
                doc_ids = list(dict.fromkeys([*doc_ids, str(ev["doc_id"])]))
            for doc_id in doc_ids:
                if not any(d.get("doc_id") == doc_id for d in documents):
                    documents.append({"doc_id": doc_id})

        for message in messages:
            if not isinstance(message, ToolMessage):
                continue
            content = str(message.content)
            for doc_id in _doc_ids_from_tool(content):
                if not any(d.get("doc_id") == doc_id for d in documents):
                    documents.append({"doc_id": doc_id})
            parsed = _parse_tool_content(content)
            if parsed and "api_calls" in parsed:
                api_calls += int(parsed.get("api_calls", 0))

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

        # === ParameterPreservingReducer — 3-phase extraction ===
        skill_context = state.get("active_skill_context") or {}
        if new_evidence and skill_context:
            try:
                from tradingagents.equity_research.runtime.parameter_extractor import (
                    extract_parameters_from_evidence,
                )
                from tradingagents.equity_research.runtime.parameter_reducer import reduce_parameters
                from tradingagents.equity_research.runtime.parameter_compiler import compile_parameter_grid
                from tradingagents.equity_research.runtime.parameter_schemas import ParameterRegistry

                current_turn = int(state.get("iterations", 0))
                extracted_params, narrative = extract_parameters_from_evidence(
                    deps,
                    new_evidence,
                    skill_context,
                    question_id=_question_id_from_state(state),
                    current_turn=current_turn,
                )

                existing_registry = ParameterRegistry.model_validate(
                    state.get("parameter_registry") or {"parameters": {}, "dimensions": []}
                )
                updated_registry = reduce_parameters(
                    existing_registry, extracted_params, current_turn
                )

                parameter_grid = compile_parameter_grid(
                    updated_registry,
                    question_id=_question_id_from_state(state),
                )

                result_param_updates: dict[str, Any] = {
                    "parameter_registry": updated_registry.model_dump(),
                    "parameter_grid": parameter_grid,
                }

                if narrative:
                    fact_store.append({
                        "question_id": _question_id_from_state(state),
                        "text": narrative,
                        "source": "parameter_extraction_narrative",
                    })
            except Exception:
                result_param_updates = {}
        else:
            result_param_updates = {}

        executor_snapshot = format_executor_messages(
            deps,
            messages,
            pending_evidence=pending,
            active_task=active_task,
            active_step=active_step,
        )

        result: dict[str, Any] = {
            **result_param_updates,
            **clear_messages_update(),
            "evidence_buffer": buffer,
            "pending_evidence": pending,
            "search_memory": search_memory,
            "documents": documents,
            "api_calls": api_calls,
            "research_plan": plan_raw,
            "research_todo_list": todo_list,
            "fact_store": fact_store,
            "calculation_store": calc_store,
            "evidence_ledger": evidence_ledger,
            "evidence_fragments": evidence_fragments,
            "active_task": active_task,
            "active_step": active_step,
            "executor_context_snapshot": executor_snapshot,
            "_executor_step_calls": 0,
            "_executor_tool_node": None,
            "_executor_tool_group": None,
        }
        if _is_synthesizer_handoff(active_step):
            result["_force_synthesize"] = True
        if errors:
            result["errors"] = errors
        result.update(deps.trace({**state, **result}, agent_trace, {
            "pending_evidence": len(pending),
            "pending_evidence_added": len(pending) - pending_before,
            "step_id": step_id,
        }))
        return result

    return apply


def create_section_executor_tools_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    nodes = build_section_executor_tool_set_nodes(deps, task_profile)
    return nodes[tool_group_node_name("retrieval")]
