"""Model-based context compaction for research prompts with LRU cache."""

from __future__ import annotations

import hashlib
from typing import Any, Mapping

from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm

_COMPACT_CACHE: dict[str, str] = {}
_COMPACT_CACHE_ORDER: list[str] = []
_COMPACT_CACHE_MAXSIZE = 256
_DEFAULT_PROMPT_CONTEXT_MAX_CHARS = 32000
# Hard ceiling for compact LLM input (OpenAI string limit is ~10MB; stay well below).
_DEFAULT_COMPACT_LLM_MAX_INPUT_CHARS = 1_000_000


def _max_chars(config: dict[str, Any] | None, key: str, default: int) -> int:
    if not config:
        return default
    er = config.get("equity_research", {}) or {}
    return int(er.get(key, default))


def resolve_prompt_context_max_chars(
    config: dict[str, Any] | None,
    *,
    max_chars: int | None = None,
) -> int:
    """Resolve the unified prompt context budget.

    Prefer explicit ``max_chars``, then ``prompt_context_max_chars``, then legacy
    ``consensus_context_max_chars`` / ``executor_context_max_chars``.
    """
    if max_chars is not None:
        return int(max_chars)
    if not config:
        return _DEFAULT_PROMPT_CONTEXT_MAX_CHARS
    er = config.get("equity_research", {}) or {}
    if "prompt_context_max_chars" in er:
        return int(er["prompt_context_max_chars"])
    if "consensus_context_max_chars" in er:
        return int(er["consensus_context_max_chars"])
    if "executor_context_max_chars" in er:
        return int(er["executor_context_max_chars"])
    return _DEFAULT_PROMPT_CONTEXT_MAX_CHARS


def resolve_compact_llm_max_input_chars(config: dict[str, Any] | None) -> int:
    return _max_chars(config, "compact_llm_max_input_chars", _DEFAULT_COMPACT_LLM_MAX_INPUT_CHARS)


def _deterministic_pretruncate(text: str, max_chars: int) -> str:
    """Shrink oversized text before sending to the compact LLM.

    Prefer keeping headings, citation markers, and the leading portion of each section.
    """
    if len(text) <= max_chars:
        return text
    # Keep head + a small tail so structure/end matter survive.
    head_budget = int(max_chars * 0.85)
    tail_budget = max_chars - head_budget - 80
    if tail_budget < 0:
        return text[:max_chars]
    omitted = len(text) - head_budget - max(tail_budget, 0)
    return (
        text[:head_budget]
        + f"\n\n...[truncated {omitted} chars for compact LLM safety]...\n\n"
        + (text[-tail_budget:] if tail_budget > 0 else "")
    )


def _cache_maxsize(config: dict[str, Any] | None) -> int:
    return _max_chars(config, "compact_cache_size", _COMPACT_CACHE_MAXSIZE)


def _compact_cache_key(text: str, purpose: str, limit: int, model_id: str) -> str:
    digest = hashlib.sha256(text.encode()).hexdigest()[:16]
    return f"{purpose}|{limit}|{model_id}|{digest}"


def clear_compact_cache() -> None:
    """Clear the in-process compact result cache (for tests)."""
    _COMPACT_CACHE.clear()
    _COMPACT_CACHE_ORDER.clear()


def _cache_get(key: str) -> str | None:
    return _COMPACT_CACHE.get(key)


def _cache_set(key: str, value: str, maxsize: int) -> None:
    if key in _COMPACT_CACHE:
        _COMPACT_CACHE_ORDER.remove(key)
    elif len(_COMPACT_CACHE_ORDER) >= maxsize:
        oldest = _COMPACT_CACHE_ORDER.pop(0)
        _COMPACT_CACHE.pop(oldest, None)
    _COMPACT_CACHE[key] = value
    _COMPACT_CACHE_ORDER.append(key)


def _invoke_compact_llm(llm: Any, prompt: str) -> str:
    response = llm.invoke(prompt)
    return response.content if hasattr(response, "content") else str(response)


def compact_if_needed(
    deps: Any,
    text: str,
    *,
    purpose: str,
    compact_prompt_block: str | None = None,
    max_chars: int | None = None,
) -> str:
    config = getattr(deps, "config", None)
    limit = resolve_prompt_context_max_chars(config, max_chars=max_chars)
    if len(text) <= limit:
        return text

    llm = resolve_research_llm(deps, "nano")
    model_id = getattr(llm, "model_name", None) or getattr(llm, "model", None) or str(id(llm))
    cache_key = _compact_cache_key(text, purpose, limit, str(model_id))

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # Hard guard: never send multi-MB raw blobs to the compact LLM.
    llm_input_cap = resolve_compact_llm_max_input_chars(config)
    safe_text = _deterministic_pretruncate(text, llm_input_cap)

    prompt = (
        f"Compress the following {purpose} for an equity research agent.\n"
        "Requirements:\n"
        "- Keep ALL citation markers like [1] and URLs verbatim when present\n"
        "- Keep numeric estimates and dimension labels\n"
        "- Use bullet lists, not JSON\n"
        "- If given a table, only compress the text content. Please preserve the table structure\n"
        f"- Target length: under {limit} characters\n"
        f"{compact_prompt_block or 'Use your best judgment to summarize and compress the content.'}\n"
        f"------\n\n"
        f"{safe_text}"
    )
    # Also guard the full prompt size (instructions + text).
    prompt_cap = llm_input_cap + 4000
    if len(prompt) > prompt_cap:
        # Fall back to deterministic truncation as the compact result.
        result = _deterministic_pretruncate(text, limit)
        _cache_set(cache_key, result, _cache_maxsize(config))
        return result

    result = _invoke_compact_llm(llm, prompt)
    _cache_set(cache_key, result, _cache_maxsize(config))
    return result


def compact_prompt_block(
    deps: Any,
    text: str,
    *,
    purpose: str,
    summarize_prompt: str | None = None,
    max_chars: int | None = None,
) -> str:
    """Thin wrapper for prompt injection blocks."""
    if not text:
        return text
    return compact_if_needed(
        deps,
        text,
        purpose=purpose,
        max_chars=max_chars,
        compact_prompt_block=summarize_prompt,
    )


def assemble_context_block(sections: Mapping[str, str]) -> str:
    """Join labeled non-empty sections into one context block (no compaction)."""
    parts: list[str] = []
    for label, text in sections.items():
        body = (text or "").strip()
        if not body:
            continue
        parts.append(f"### {label}\n{body}")
    return "\n\n".join(parts)


def assemble_and_compact_context(
    deps: Any,
    sections: Mapping[str, str],
    *,
    purpose: str,
    max_chars: int | None = None,
    compact_prompt_block: str | None = None,
) -> str:
    """Assemble labeled sections, then compact at most once if over budget."""
    assembled = assemble_context_block(sections)
    if not assembled:
        return ""
    return compact_if_needed(
        deps,
        assembled,
        purpose=purpose,
        max_chars=max_chars,
        compact_prompt_block=compact_prompt_block,
    )
