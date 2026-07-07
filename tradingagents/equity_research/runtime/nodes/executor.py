"""Batch search executor nodes for research subgraphs."""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.prebuilt import ToolNode

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.messages import clear_messages_update
from tradingagents.equity_research.runtime.utils.search_memory import (
    append_search_record,
    queries_from_memory,
)
from tradingagents.equity_research.state.consensus_schemas import SearchRecord
from tradingagents.equity_research.tools.search_tools import _batch_concurrency

BATCH_PERPLEXITY_TOOL_NAME = "batch_perplexity_search"


def _append_documents(documents: list[dict], doc_ids: list[str]) -> list[dict]:
    new_docs = list(documents)
    existing_doc_ids = {d.get("doc_id") for d in new_docs}
    for doc_id in doc_ids:
        if doc_id not in existing_doc_ids:
            new_docs.append({"doc_id": doc_id})
            existing_doc_ids.add(doc_id)
    return new_docs


def build_executor_tools(
    deps: EquityResearchDeps,
    *,
    search_fn: Callable[..., Any] | None = None,
    extra: list[BaseTool] | None = None,
) -> list[BaseTool]:
    from tradingagents.equity_research.tools.lc.search import make_batch_perplexity_search_tool

    tools: list[BaseTool] = [make_batch_perplexity_search_tool(deps, search_fn=search_fn)]
    if extra:
        tools.extend(extra)
    return tools


def create_executor_tools_node(
    deps: EquityResearchDeps,
    *,
    search_fn: Callable[..., Any] | None = None,
    extra: list[BaseTool] | None = None,
):
    return ToolNode(build_executor_tools(deps, search_fn=search_fn, extra=extra))


def executor_router(state: dict[str, Any]) -> str:
    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return str(state.get("_executor_tool_node", "executor_tools"))
    return "apply"


def _parse_batch_search_result(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"items": [], "api_calls": 0, "errors": [f"invalid tool result: {content[:120]}"]}


def _latest_batch_tool_result(messages: list[Any]) -> dict[str, Any] | None:
    for message in reversed(messages):
        if isinstance(message, ToolMessage):
            parsed = _parse_batch_search_result(str(message.content))
            if parsed.get("items") is not None:
                return parsed
    return None


def create_executor_dispatch_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    batch_size: int = 5,
    tool_node_name: str = "executor_tools",
):
    def executor_dispatch(state: dict[str, Any]) -> dict[str, Any]:
        queue = list(state.get("query_queue", []))
        if not queue:
            return {}

        queue.sort(key=lambda q: int(q.get("priority", 0)), reverse=True)
        to_run = queue[:batch_size]
        remaining = queue[batch_size:]
        ticker = state.get("ticker", "")
        iteration = int(state.get("iterations", state.get("consensus_iterations", 0)))
        search_memory = list(state.get("search_memory", []))

        tool_call_id = f"batch_{uuid.uuid4().hex[:8]}"
        return {
            "query_queue": remaining,
            "_executor_tool_node": tool_node_name,
            "_executor_batch": {
                "batch_size": len(to_run),
                "to_run": to_run,
                "tool_call_id": tool_call_id,
            },
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "id": tool_call_id,
                        "name": BATCH_PERPLEXITY_TOOL_NAME,
                        "args": {
                            "ticker": ticker,
                            "queries": to_run,
                            "iteration": iteration,
                            "search_memory": search_memory,
                        },
                    }],
                ),
            ],
        }

    return executor_dispatch


def create_executor_apply_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    trace_name: str | None = None,
):
    agent_trace = trace_name or f"{task_profile.task_id}_query_executor"

    def executor_apply(state: dict[str, Any]) -> dict[str, Any]:
        batch_meta = state.get("_executor_batch")
        batch_result = _latest_batch_tool_result(state.get("messages", []))
        if not batch_meta and not batch_result:
            return clear_messages_update()

        errors = list(state.get("errors", []))
        search_memory = list(state.get("search_memory", []))
        buffer = list(state.get("evidence_buffer", []))
        pending = list(state.get("pending_evidence", []))
        new_docs = list(state.get("documents", []))
        api_calls = int(state.get("api_calls", 0))
        dimensions_run: list[str] = []

        batch_result = batch_result or {"items": [], "api_calls": 0, "errors": []}

        errors.extend(batch_result.get("errors") or [])
        api_calls += int(batch_result.get("api_calls", 0))

        items = list(batch_result.get("items") or [])
        batch_size = int((batch_meta or {}).get("batch_size", 0)) or len(items) or 1
        concurrency = _batch_concurrency(deps, batch_size)

        items.sort(key=lambda item: int(item.get("priority", 0)), reverse=True)

        for item in items:
            dimensions_run.append(item.get("target_dimension", "narrative_framework"))
            if item.get("error"):
                errors.append(str(item["error"]))
                continue
            evidence = item.get("evidence")
            record = item.get("record")
            if not evidence or not record:
                continue
            buffer.append(evidence)
            pending.append(evidence)
            search_memory = append_search_record(search_memory, SearchRecord(**record))
            new_docs = _append_documents(new_docs, list(item.get("doc_ids") or []))

        executed = queries_from_memory(search_memory)
        updates: dict[str, Any] = {
            "query_queue": list(state.get("query_queue", [])),
            "executed_queries": executed,
            "search_memory": search_memory,
            "evidence_buffer": buffer,
            "pending_evidence": pending,
            "documents": new_docs,
            "api_calls": api_calls,
            **clear_messages_update(),
            "_executor_tool_node": None,
            "_executor_batch": None,
        }
        if errors:
            updates["errors"] = errors
        updates.update(deps.trace({**state, **updates}, agent_trace, {
            "batch_size": batch_size,
            "dimensions": dimensions_run,
            "concurrency": concurrency,
        }))
        return updates

    return executor_apply


def create_executor_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    batch_size: int = 5,
    trace_name: str | None = None,
    search_fn: Callable[..., Any] | None = None,
):
    dispatch = create_executor_dispatch_node(deps, task_profile, batch_size=batch_size)
    tools = create_executor_tools_node(deps, search_fn=search_fn)
    apply = create_executor_apply_node(deps, task_profile, trace_name=trace_name)

    def query_batch_executor(state: dict[str, Any]) -> dict[str, Any]:
        try:
            dispatch_updates = dispatch(state)
            if not dispatch_updates:
                return {}
            working = {**state, **dispatch_updates}
            if executor_router(working) != "apply":
                working = {**working, **tools.invoke(working)}
            return apply(working)
        except Exception as exc:
            errors = list(state.get("errors", []))
            errors.append(f"query_batch_executor: {exc}")
            return {
                "errors": errors,
                "query_queue": list(state.get("query_queue", [])),
                "evidence_buffer": list(state.get("evidence_buffer", [])),
                "pending_evidence": list(state.get("pending_evidence", [])),
                "search_memory": list(state.get("search_memory", [])),
                "documents": list(state.get("documents", [])),
                "api_calls": int(state.get("api_calls", 0)),
            }

    return query_batch_executor
