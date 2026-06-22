"""E2E smoke test with mocked LLM and external services."""

from unittest.mock import MagicMock, patch

import pytest

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.graph.equity_research_graph import EquityResearchGraph
from tradingagents.equity_research.state.schemas import ClaimStatus


def _mock_llm_response(text: str = "Analysis content."):
    resp = MagicMock()
    resp.content = text
    return resp


@pytest.mark.integration
def test_e2e_mini_report_mocked():
    config = {
        "llm_provider": "openai",
        "deep_think_llm": "gpt-4o-mini",
        "quick_think_llm": "gpt-4o-mini",
        "postgres_url": "postgresql+psycopg://localhost/test_skip",
        "equity_research": {
            "max_hypothesis_iterations": 1,
            "max_hypotheses_per_section": 2,
            "budget": {"max_search_queries": 1, "max_extraction_docs": 1},
            "embedding_provider": "hash",
        },
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _mock_llm_response(
        '[{"statement": "Growth thesis", "consensus_view": "moderate", '
        '"variant_view": "accelerating", "required_evidence": ["revenue"]}]'
    )

    with patch("tradingagents.equity_research.graph.equity_research_graph.create_llm_client") as mock_client:
        client_inst = MagicMock()
        client_inst.get_llm.return_value = mock_llm
        mock_client.return_value = client_inst
        with patch("tradingagents.equity_research.graph.equity_research_graph.init_db"):
            with patch("tradingagents.equity_research.integrations.perplexity.PerplexityClient.search") as mock_search:
                mock_search.return_value = {
                    "answer": "NVDA is a leading AI chip company.",
                    "citations": ["https://example.com/nvda"],
                }
                with patch("tradingagents.agents.utils.agent_utils.resolve_instrument_identity") as mock_id:
                    mock_id.return_value = {"name": "NVIDIA", "sector": "Technology", "industry": "Semiconductors"}
                    with patch("yfinance.Ticker") as mock_yf:
                        mock_yf.return_value.info = {"currentPrice": 100.0, "currency": "USD"}
                        graph = EquityResearchGraph(config={**config, "equity_research_use_memory": True}, init_database=False)
                        graph.deps.quick_llm = mock_llm
                        graph.deps.deep_llm = mock_llm
                        final_state, _ = graph.propagate("NVDA")

    assert final_state.get("final_report")
    assert len(final_state.get("completed_sections", [])) >= 1
    verified = [c for c in final_state.get("claims", []) if c.get("status") == ClaimStatus.VERIFIED.value]
    assert final_state.get("rating") is not None or final_state.get("target_price") is not None
    assert final_state.get("research_traces")
