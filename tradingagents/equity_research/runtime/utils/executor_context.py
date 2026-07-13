"""Format executor ReAct context for reflector prompts."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from tradingagents.equity_research.runtime.utils.context_compact import (
    assemble_and_compact_context,
)


def _tool_content_summary(content: str) -> str:
    """Extract a dialogue-side summary from a tool result payload."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        text = content.strip()
        return text if len(text) <= 800 else text[:797] + "..."
    if not isinstance(data, dict):
        text = str(data)
        return text if len(text) <= 800 else text[:797] + "..."

    parts: list[str] = []
    if data.get("summary"):
        parts.append(str(data["summary"]))
    if data.get("status"):
        parts.append(f"status={data['status']}")
    items = data.get("items")
    if isinstance(items, list):
        parts.append(f"items={len(items)}")
        for item in items[:3]:
            if isinstance(item, dict):
                ev = item.get("evidence") or item
                snippet = ev.get("quote") or ev.get("answer") or ev.get("text") or ""
                if snippet:
                    snippet = str(snippet)
                    parts.append(snippet if len(snippet) <= 200 else snippet[:197] + "...")
    if data.get("answer"):
        answer = str(data["answer"])
        parts.append(answer if len(answer) <= 400 else answer[:397] + "...")
    if data.get("error"):
        parts.append(f"error={data['error']}")
    if not parts and data.get("text"):
        text = str(data["text"])
        parts.append(text if len(text) <= 400 else text[:397] + "...")
    return " | ".join(parts) if parts else "ok"


def slim_tool_message_content(content: str, *, tool_name: str = "tool") -> str:
    """Replace full tool payload with call/result summary for dialogue history."""
    summary = _tool_content_summary(content)
    return json.dumps(
        {
            "slimmed": True,
            "tool": tool_name,
            "summary": summary,
        },
        ensure_ascii=False,
    )


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
                call_bits = []
                for tc in tool_calls:
                    name = tc.get("name", "")
                    args = tc.get("args") or {}
                    call_bits.append(f"{name}({json.dumps(args, default=str)})")
                lines.append("Assistant tool calls: " + "; ".join(call_bits))
            elif msg.content:
                lines.append(f"Assistant: {msg.content}")
        elif isinstance(msg, ToolMessage):
            name = getattr(msg, "name", None) or "tool"
            raw = str(msg.content)
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict) and parsed.get("slimmed"):
                summary = parsed.get("summary", "")
            else:
                summary = _tool_content_summary(raw)
            lines.append(f"Tool [{name}] result summary: {summary}")

    pending_block = ""
    if pending_evidence:
        # Dialogue side keeps recent evidence summaries only; full text is in state.
        ev_lines = []
        for ev in pending_evidence[-8:]:
            snippet = str(ev.get("snippet") or ev.get("content") or ev.get("answer") or "")
            if len(snippet) > 300:
                snippet = snippet[:297] + "..."
            ev_lines.append(
                f"- [{ev.get('source', 'unknown')}] q={ev.get('question_id', '')} {snippet}"
            )
        pending_block = "\n".join(ev_lines)

    return assemble_and_compact_context(
        deps,
        {
            "Executor dialogue (calls + result summaries)": "\n\n".join(lines),
            "Pending evidence summaries": pending_block,
        },
        purpose="full executor context for reflector",
    )
