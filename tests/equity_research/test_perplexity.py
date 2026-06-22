"""Integration tests for Perplexity client with mocked ChatPerplexity."""

from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage

from tradingagents.llm_clients.perplexity_client import PerplexityClient, SearchMode


def test_perplexity_search_registers_citations():
    client = PerplexityClient("sonar-pro", config={"perplexity_api_key": "test-key"})
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = AIMessage(
        content="NVDA revenue grew.",
        additional_kwargs={"citations": ["https://example.com/article"]},
    )
    with patch.object(client, "get_llm", return_value=mock_llm):
        result = client.search("NVDA outlook", mode=SearchMode.EXPLORATORY)
    assert "NVDA" in result["query"] or result.get("answer")
    assert result["citations"] == ["https://example.com/article"]
