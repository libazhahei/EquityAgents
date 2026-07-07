"""LLM invocation with rate-limit retry for equity research nodes."""

from __future__ import annotations

import logging
import random
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

_RETRY_AFTER_MESSAGE_RE = re.compile(
    r"try again in\s+(\d+(?:\.\d+)?)\s*s",
    re.IGNORECASE,
)

_DEFAULT_MAX_ATTEMPTS = 5
_DEFAULT_BASE_DELAY = 2.0
_DEFAULT_MAX_DELAY = 60.0


def _equity_research_config(deps: Any | None) -> dict[str, Any]:
    if deps is None:
        return {}
    config = getattr(deps, "config", None) or {}
    er = config.get("equity_research", {})
    return er if isinstance(er, dict) else {}


def _retry_settings(deps: Any | None, max_attempts: int | None) -> tuple[int, float, float]:
    er = _equity_research_config(deps)
    attempts = max_attempts if max_attempts is not None else int(
        er.get("llm_rate_limit_max_retries", _DEFAULT_MAX_ATTEMPTS)
    )
    base_delay = float(er.get("llm_rate_limit_base_delay", _DEFAULT_BASE_DELAY))
    max_delay = float(er.get("llm_rate_limit_max_delay", _DEFAULT_MAX_DELAY))
    return max(1, attempts), base_delay, max_delay


def _is_rate_limit_error(exc: BaseException) -> bool:
    try:
        from openai import RateLimitError

        if isinstance(exc, RateLimitError):
            return True
    except ImportError:
        pass

    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True

    message = str(exc).lower()
    return "rate_limit" in message or "rate limit" in message


def _retry_after_from_headers(exc: BaseException) -> float | None:
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After") or headers.get("retry-after")
        if raw is None:
            return None
        return float(raw)
    except (TypeError, ValueError):
        return None


def _retry_after_from_message(exc: BaseException) -> float | None:
    match = _RETRY_AFTER_MESSAGE_RE.search(str(exc))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _fallback_backoff(attempt: int, base_delay: float, max_delay: float) -> float:
    delay = min(base_delay * (2 ** attempt), max_delay)
    jitter = random.uniform(0, delay * 0.1)
    return delay + jitter


def _compute_wait_seconds(
    exc: BaseException,
    attempt: int,
    base_delay: float,
    max_delay: float,
) -> float:
    for parser in (_retry_after_from_headers, _retry_after_from_message):
        wait = parser(exc)
        if wait is not None and wait > 0:
            return min(wait, max_delay)
    return _fallback_backoff(attempt, base_delay, max_delay)


def invoke_llm_with_retry(
    llm: Any,
    input_: Any,
    *,
    deps: Any | None = None,
    agent_name: str = "llm",
    max_attempts: int | None = None,
) -> Any:
    """Invoke an LLM, retrying on transient rate-limit errors with backoff."""
    attempts, base_delay, max_delay = _retry_settings(deps, max_attempts)

    for attempt in range(attempts):
        try:
            return llm.invoke(input_)
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt >= attempts - 1:
                raise

            wait = _compute_wait_seconds(exc, attempt, base_delay, max_delay)
            logger.warning(
                "%s: rate limited (%s); waiting %.1fs before retry %d/%d",
                agent_name,
                exc,
                wait,
                attempt + 2,
                attempts,
            )
            time.sleep(wait)

    raise RuntimeError(f"{agent_name}: exhausted rate-limit retries")
