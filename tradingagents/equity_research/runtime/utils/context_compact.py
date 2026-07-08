"""Model-based context compaction for research prompts with LRU cache."""

from __future__ import annotations

import hashlib
from functools import lru_cache
from typing import Any

from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm

_COMPACT_CACHE: dict[str, str] = {}
_COMPACT_CACHE_ORDER: list[str] = []
_COMPACT_CACHE_MAXSIZE = 256


def _max_chars(config: dict[str, Any] | None, key: str, default: int) -> int:
    if not config:
        return default
    er = config.get("equity_research", {})
    return int(er.get(key, default))


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
    limit = max_chars or _max_chars(
        config,
        "consensus_context_max_chars",
        6000,
    )
    if len(text) <= limit:
        return text

    llm = resolve_research_llm(deps, "nano")
    model_id = getattr(llm, "model_name", None) or getattr(llm, "model", None) or str(id(llm))
    cache_key = _compact_cache_key(text, purpose, limit, str(model_id))

    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    prompt = (
        f"Compress the following {purpose} for an equity research agent.\n"
        "Requirements:\n"
        "- Keep ALL citation URLs verbatim\n"
        "- Keep numeric estimates and dimension labels\n"
        "- Use bullet lists, not JSON\n"
        "- If given a table, only compress the text content. Please preserve the table structure\n"
        f"- Target length: under {limit} characters\n"
        f"{compact_prompt_block or 'Use your best judgment to summarize and compress the content.'}\n"
        f"------\n\n"
        f"{text}"
    )
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
    return compact_if_needed(deps, text, purpose=purpose, max_chars=max_chars, compact_prompt_block=summarize_prompt)
