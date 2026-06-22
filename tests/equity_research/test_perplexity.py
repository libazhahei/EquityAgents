"""Integration tests for Perplexity client with mocked HTTP."""

from unittest.mock import MagicMock, patch

from tradingagents.equity_research.integrations.perplexity import PerplexityClient, SearchMode


def test_perplexity_search_registers_citations():
    client = PerplexityClient({"perplexity_api_key": "test-key"})
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"url": "https://example.com/article", "snippet": "NVDA revenue grew."},
        ]
    }
    with patch.object(client.redis, "rate_limit", return_value=True):
        with patch("httpx.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value = mock_client
            result = client.search("NVDA outlook", mode=SearchMode.EXPLORATORY)
    assert "NVDA" in result["query"] or result.get("answer")
    assert result["citations"] == ["https://example.com/article"]
