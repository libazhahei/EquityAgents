"""Model-based context compaction for consensus prompts."""

from __future__ import annotations

from typing import Any


def _max_chars(config: dict[str, Any] | None, key: str, default: int) -> int:
    if not config:
        return default
    er = config.get("equity_research", {})
    return int(er.get(key, default))


def compact_if_needed(
    deps: Any,
    text: str,
    *,
    purpose: str,
    max_chars: int | None = None,
) -> str:
    limit = max_chars or _max_chars(
        getattr(deps, "config", None),
        "consensus_context_max_chars",
        6000,
    )
    if len(text) <= limit:
        return text
    prompt = (
        f"Compress the following {purpose} for an equity research agent.\n"
        "Requirements:\n"
        "- Keep ALL citation URLs verbatim\n"
        "- Keep numeric estimates and dimension labels\n"
        "- Use bullet lists, not JSON\n"
        f"- Target length: under {limit} characters\n\n"
        f"{text}"
    )
    response = deps.quick_llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)
