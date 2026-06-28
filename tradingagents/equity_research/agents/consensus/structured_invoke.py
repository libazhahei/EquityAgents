"""Structured LLM invocation with LangChain retry for consensus nodes."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from tradingagents.agents.utils.structured import bind_structured

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_RUNNABLE_CACHE: dict[tuple[int, str], Any] = {}


class StructuredOutputUnsupported(Exception):
    """Raised when the LLM provider does not support structured output."""


def _cache_key(llm: Any, schema: type[BaseModel]) -> tuple[int, str]:
    return (id(llm), schema.__name__)


def get_structured_runnable(
    llm: Any,
    schema: type[T],
    agent_name: str,
    *,
    max_attempts: int = 3,
) -> Any:
    key = _cache_key(llm, schema)
    if key not in _RUNNABLE_CACHE:
        structured = bind_structured(llm, schema, agent_name)
        if structured is None:
            raise StructuredOutputUnsupported(f"{agent_name}: structured output unsupported")
        _RUNNABLE_CACHE[key] = structured.with_retry(
            stop_after_attempt=max_attempts,
            retry_if_exception_type=(ValidationError, ValueError, TypeError),
        )
    return _RUNNABLE_CACHE[key]


def invoke_structured_with_retry(
    llm: Any,
    schema: type[T],
    prompt: str,
    *,
    agent_name: str,
    max_attempts: int = 3,
    fallback: Callable[[], T] | None = None,
) -> T:
    try:
        runnable = get_structured_runnable(
            llm, schema, agent_name, max_attempts=max_attempts,
        )
        result = runnable.invoke(prompt)
        return schema.model_validate(result)
    except Exception as exc:
        logger.warning("%s: structured invocation failed (%s)", agent_name, exc)
        if fallback is not None:
            return fallback()
        raise
