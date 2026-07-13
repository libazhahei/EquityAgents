"""Format executor ReAct context for reflector prompts; lazy tool-message slimming."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import AIMessage, ToolMessage

from tradingagents.equity_research.runtime.utils.context_compact import (
    assemble_and_compact_context,
    resolve_prompt_context_max_chars,
)

# Write offloads facts to disk — always collapse dialogue to "ok".
# Read must keep full items until over budget (then lazy-slim like other tools).
_FINDINGS_CACHE_WRITE_TOOLS = frozenset({"findings_cache_write"})


def _tool_content_summary(content: str, *, tool_name: str = "tool") -> str:
    """Extract a dialogue-side summary from a tool result payload."""
    if tool_name in _FINDINGS_CACHE_WRITE_TOOLS:
        return "ok"
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        text = content.strip()
        return text if len(text) <= 800 else text[:797] + "..."
    if not isinstance(data, dict):
        text = str(data)
        return text if len(text) <= 800 else text[:797] + "..."

    parts: list[str] = []
    if data.get("summary") and str(data.get("summary")).lower() != "ok":
        parts.append(str(data["summary"]))
    elif data.get("summary") == "ok" and tool_name in _FINDINGS_CACHE_WRITE_TOOLS:
        return "ok"
    if data.get("status"):
        parts.append(f"status={data['status']}")
    if data.get("error"):
        parts.append(f"error={data['error']}")

    # Financial / structured payloads
    for key in (
        "statement_type", "period", "fiscal_period", "ticker", "symbol",
        "filing_type", "form", "accession", "url", "path", "count",
    ):
        if data.get(key) not in (None, ""):
            parts.append(f"{key}={data[key]}")

    # Nested data tables / rows
    for key in ("data", "rows", "statements", "results", "records", "metrics"):
        val = data.get(key)
        if isinstance(val, list) and val:
            parts.append(f"{key}={len(val)}")
            sample = val[0]
            if isinstance(sample, dict):
                preview = {k: sample[k] for k in list(sample)[:8]}
                preview_s = json.dumps(preview, default=str, ensure_ascii=False)
                parts.append(preview_s if len(preview_s) <= 400 else preview_s[:397] + "...")
            break
        if isinstance(val, dict) and val:
            preview_s = json.dumps({k: val[k] for k in list(val)[:12]}, default=str, ensure_ascii=False)
            parts.append(f"{key}={preview_s}" if len(preview_s) <= 500 else f"{key}={preview_s[:497]}...")
            break

    items = data.get("items")
    if isinstance(items, list):
        parts.append(f"items={len(items)}")
        for item in items[:3]:
            if isinstance(item, dict):
                ev = item.get("evidence") or item
                snippet = (
                    ev.get("quote") or ev.get("answer") or ev.get("text")
                    or ev.get("claim") or ev.get("snippet") or ""
                )
                if snippet:
                    snippet = str(snippet)
                    parts.append(snippet if len(snippet) <= 200 else snippet[:197] + "...")

    if data.get("answer"):
        answer = str(data["answer"])
        parts.append(answer if len(answer) <= 400 else answer[:397] + "...")
    if not parts and data.get("text"):
        text = str(data["text"])
        parts.append(text if len(text) <= 400 else text[:397] + "...")
    if not parts:
        # Last resort: compact JSON preview instead of opaque "ok"
        preview = json.dumps(data, default=str, ensure_ascii=False)
        return preview if len(preview) <= 600 else preview[:597] + "..."
    return " | ".join(parts)


def slim_tool_message_content(content: str, *, tool_name: str = "tool") -> str:
    """Replace full tool payload with call/result summary for dialogue history."""
    summary = _tool_content_summary(content, tool_name=tool_name)
    return json.dumps(
        {
            "slimmed": True,
            "tool": tool_name,
            "summary": summary,
        },
        ensure_ascii=False,
    )


def _message_chars(messages: list[Any]) -> int:
    total = 0
    for msg in messages:
        content = getattr(msg, "content", "") or ""
        total += len(str(content))
        if isinstance(msg, AIMessage) and msg.tool_calls:
            total += len(json.dumps(msg.tool_calls, default=str))
    return total


def compact_tool_messages_if_needed(
    messages: list[Any],
    *,
    max_chars: int,
    force_tools: frozenset[str] | None = None,
) -> tuple[list[Any], list[Any]]:
    """Keep full tool payloads until over budget; then slim older ToolMessages.

    ``findings_cache_write`` is always slimmed to summary \"ok\".
    ``findings_cache_read`` keeps full items until over budget, then lazy-slims
    with count/claim previews like other retrieval tools.
    Returns (messages, replaced_tool_messages).
    """
    force_tools = force_tools or _FINDINGS_CACHE_WRITE_TOOLS
    replaced: list[Any] = []
    out = list(messages)

    def _replace_at(idx: int, tool_name: str) -> None:
        msg = out[idx]
        if not isinstance(msg, ToolMessage):
            return
        if _is_slimmed_tool_content(msg.content):
            return
        kwargs: dict[str, Any] = {
            "content": slim_tool_message_content(str(msg.content), tool_name=tool_name),
            "tool_call_id": msg.tool_call_id,
            "name": tool_name,
        }
        msg_id = getattr(msg, "id", None)
        if msg_id is not None:
            kwargs["id"] = msg_id
        replacement = ToolMessage(**kwargs)
        out[idx] = replacement
        replaced.append(replacement)

    # Always slim findings_cache_write (offload ack only).
    for i, msg in enumerate(out):
        if isinstance(msg, ToolMessage):
            name = getattr(msg, "name", None) or "tool"
            if name in force_tools:
                _replace_at(i, name)

    if _message_chars(out) <= max_chars:
        return out, replaced

    # Slim oldest non-slimmed ToolMessages first (exclude the most recent tool result).
    tool_indices = [
        i for i, msg in enumerate(out)
        if isinstance(msg, ToolMessage) and not _is_slimmed_tool_content(msg.content)
    ]
    # Keep the newest tool message full if possible.
    for idx in tool_indices[:-1]:
        name = getattr(out[idx], "name", None) or "tool"
        _replace_at(idx, name)
        if _message_chars(out) <= max_chars:
            break
    else:
        if tool_indices:
            idx = tool_indices[-1]
            name = getattr(out[idx], "name", None) or "tool"
            _replace_at(idx, name)

    return out, replaced


def _is_slimmed_tool_content(content: Any) -> bool:
    if isinstance(content, str):
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return False
        return isinstance(data, dict) and bool(data.get("slimmed"))
    return isinstance(content, dict) and bool(content.get("slimmed"))


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
                summary = _tool_content_summary(raw, tool_name=name)
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
            "Pending evidence (recent)": pending_block,
        },
        purpose="executor context snapshot",
    )
