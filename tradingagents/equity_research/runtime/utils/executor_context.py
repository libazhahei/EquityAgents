"""Format executor ReAct context for reflector prompts."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from tradingagents.equity_research.runtime.utils.context_compact import (
    _max_chars,
    compact_prompt_block,
)


def _tool_content_summary(content: str) -> str:
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return content
    if not isinstance(data, dict):
        return content
    parts: list[str] = []
    if data.get("summary"):
        parts.append(str(data["summary"]))
    items = data.get("items")
    if isinstance(items, list):
        for item in items[:10]:
            if isinstance(item, dict):
                ev = item.get("evidence") or item
                snippet = ev.get("quote") or ev.get("answer") or ev.get("text") or str(item)
                parts.append(str(snippet))
    if data.get("answer"):
        parts.append(str(data["answer"]))
    if data.get("text"):
        parts.append(str(data["text"]))
    return "\n".join(parts) if parts else content


def format_executor_messages(
    deps: Any,
    messages: list[Any],
    *,
    pending_evidence: list[dict] | None = None,
    active_task: dict[str, Any] | None = None,
    active_step: dict[str, Any] | None = None,
) -> str:
    lines: list[str] = []
    if active_task:
        lines.append(f"Active task: {json.dumps(active_task)}")
    if active_step:
        lines.append(f"Active step: {json.dumps(active_step)}")

    for msg in messages:
        if isinstance(msg, AIMessage):
            tool_calls = msg.tool_calls or []
            if tool_calls:
                names = [tc.get("name", "") for tc in tool_calls]
                lines.append(f"Assistant tool calls: {', '.join(names)}")
            elif msg.content:
                lines.append(f"Assistant: {msg.content}")
        elif isinstance(msg, ToolMessage):
            name = getattr(msg, "name", None) or "tool"
            raw = str(msg.content)
            summary = _tool_content_summary(raw)
            block = compact_prompt_block(
                deps,
                summary,
                purpose=f"executor tool result ({name})",
            )
            lines.append(f"Tool [{name}] result:\n{block}")

    if pending_evidence:
        ev_lines = []
        for ev in pending_evidence[-8:]:
            ev_lines.append(
                compact_prompt_block(
                    deps,
                    json.dumps(ev, default=str),
                    purpose="pending evidence for executor context",
                )
            )
        lines.append("Pending evidence:\n" + "\n".join(ev_lines))

    combined = "\n\n".join(lines)
    if not combined.strip():
        return ""

    config = getattr(deps, "config", None)
    total_limit = _max_chars(config, "executor_context_max_chars", 6000)
    if len(combined) <= total_limit:
        return combined
    return compact_prompt_block(
        deps,
        combined,
        purpose="full executor context for reflector",
        max_chars=total_limit,
    )
