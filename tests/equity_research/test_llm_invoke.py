"""Tests for LLM rate-limit retry utility."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from langchain_core.messages import AIMessage
from openai import RateLimitError

from tradingagents.equity_research.runtime.utils import llm_invoke
from tradingagents.equity_research.runtime.utils.llm_invoke import invoke_llm_with_retry


def _rate_limit_error(
    message: str = "Rate limit reached. Please try again in 1.722s.",
    *,
    retry_after: str | None = None,
) -> RateLimitError:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    response = httpx.Response(
        429,
        headers=headers,
        request=httpx.Request("POST", "https://api.openai.com/v1/responses"),
    )
    return RateLimitError(message, response=response, body={"error": {"message": message}})


def test_retries_on_rate_limit_then_succeeds():
    llm = MagicMock()
    llm.invoke.side_effect = [
        _rate_limit_error(),
        AIMessage(content="done"),
    ]
    deps = MagicMock()
    deps.config = {"equity_research": {"llm_rate_limit_max_retries": 3}}

    with patch.object(llm_invoke.time, "sleep") as slept:
        result = invoke_llm_with_retry(llm, ["prompt"], deps=deps, agent_name="test")

    assert result.content == "done"
    assert llm.invoke.call_count == 2
    slept.assert_called_once()


def test_parses_retry_after_from_message():
    llm = MagicMock()
    llm.invoke.side_effect = [
        _rate_limit_error("Rate limit reached. Please try again in 1.722s."),
        AIMessage(content="ok"),
    ]

    with patch.object(llm_invoke.time, "sleep") as slept:
        invoke_llm_with_retry(llm, ["prompt"], max_attempts=3)

    slept.assert_called_once()
    wait = slept.call_args[0][0]
    assert 1.7 <= wait <= 1.8


def test_retry_after_header_is_honoured():
    llm = MagicMock()
    llm.invoke.side_effect = [
        _rate_limit_error(retry_after="12"),
        AIMessage(content="ok"),
    ]

    with patch.object(llm_invoke.time, "sleep") as slept:
        invoke_llm_with_retry(llm, ["prompt"], max_attempts=3)

    slept.assert_called_once_with(12.0)


def test_raises_after_max_attempts():
    llm = MagicMock()
    err = _rate_limit_error()
    llm.invoke.side_effect = err

    with patch.object(llm_invoke.time, "sleep"):
        with pytest.raises(RateLimitError):
            invoke_llm_with_retry(llm, ["prompt"], max_attempts=2)

    assert llm.invoke.call_count == 2


def test_non_rate_limit_raises_immediately():
    llm = MagicMock()
    llm.invoke.side_effect = ValueError("bad input")

    with patch.object(llm_invoke.time, "sleep") as slept:
        with pytest.raises(ValueError, match="bad input"):
            invoke_llm_with_retry(llm, ["prompt"], max_attempts=5)

    assert llm.invoke.call_count == 1
    slept.assert_not_called()
