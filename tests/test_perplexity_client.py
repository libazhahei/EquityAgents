"""Tests for the TradingAgents Perplexity LLM client."""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_perplexity import ChatPerplexity

from tradingagents.llm_clients.factory import create_llm_client
from tradingagents.llm_clients.perplexity_client import (
    PerplexityClient,
    SearchMode,
    generate_search_plan,
)
from tradingagents.llm_clients.validators import validate_model


@pytest.mark.unit
def test_factory_creates_perplexity_client():
    client = create_llm_client("perplexity", "sonar-pro")
    assert isinstance(client, PerplexityClient)
    assert client.model == "sonar-pro"


@pytest.mark.unit
def test_validate_known_sonar_models():
    assert validate_model("perplexity", "sonar-pro")
    assert validate_model("perplexity", "sonar-deep-research")
    assert not validate_model("perplexity", "unknown-model")


@pytest.mark.unit
def test_get_llm_returns_chat_perplexity(monkeypatch):
    monkeypatch.setenv("PERPLEXITY_API_KEY", "test-key")
    client = PerplexityClient("sonar-pro")
    llm = client.get_llm()
    assert isinstance(llm, ChatPerplexity)
    assert llm.model == "sonar-pro"


@pytest.mark.unit
def test_search_returns_citations():
    client = PerplexityClient("sonar-pro", api_key="test-key")
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="NVDA revenue grew.",
        additional_kwargs={"citations": ["https://example.com/article"]},
    )
    with patch.object(client, "get_llm", return_value=mock_llm):
        result = client.search("NVDA outlook", mode=SearchMode.EXPLORATORY)
    assert result["citations"] == ["https://example.com/article"]
    assert "NVDA revenue grew." in result["answer"]


@pytest.mark.unit
def test_search_delegates_to_chat_search():
    client = PerplexityClient("sonar-pro", api_key="test-key")
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="Targeted answer",
        additional_kwargs={"citations": ["https://example.com/targeted"]},
    )
    with patch.object(client, "get_llm", return_value=mock_llm):
        result = client.search("NVDA outlook", mode=SearchMode.TARGETED)
    assert result["answer"] == "Targeted answer"
    assert result["citations"] == ["https://example.com/targeted"]
    mock_llm.invoke.assert_called_once()


@pytest.mark.unit
def test_search_respects_rate_limiter():
    client = PerplexityClient(
        "sonar-pro",
        api_key="test-key",
        rate_limiter=lambda: False,
    )
    result = client.search("NVDA outlook", mode=SearchMode.EXPLORATORY)
    assert result["rate_limited"] is True
    assert result["citations"] == []


@pytest.mark.unit
def test_from_config_reads_equity_research_settings():
    client = PerplexityClient.from_config({
        "perplexity_api_key": "cfg-key",
        "equity_research": {"perplexity_model": "sonar"},
    })
    assert client.model == "sonar"
    assert client.api_key == "cfg-key"


@pytest.mark.unit
def test_generate_search_plan_modes():
    hypothesis = {
        "hypothesis_id": "h1",
        "statement": "Revenue will grow",
        "required_evidence": ["margin expansion"],
    }
    exploratory = generate_search_plan("NVDA", hypothesis, SearchMode.EXPLORATORY, 2)
    targeted = generate_search_plan("NVDA", hypothesis, SearchMode.TARGETED, 2)
    contradiction = generate_search_plan("NVDA", hypothesis, SearchMode.CONTRADICTION, 2)
    assert len(exploratory) == 2
    assert exploratory[0]["hypothesis_id"] == "h1"
    assert "margin expansion" in targeted[0]["query"]
    assert "risks" in contradiction[0]["query"]
