"""E2E smoke test with mocked LLM and external services."""

from unittest.mock import MagicMock, patch

import pytest

from tradingagents.equity_research.graph.equity_research_graph import EquityResearchGraph


def _mock_llm_response(text: str = "Analysis content."):
    resp = MagicMock()
    resp.content = text
    return resp


def _ic_always_pass(_deps):
    def investment_committee_review(state):
        return {
            "ic_review": {
                "passed": True,
                "score": 0.9,
                "blocking_issues": [],
                "warnings": [],
                "rating": state.get("rating", "Buy"),
                "target_price": state.get("target_price", 120.0),
            },
        }
    return investment_committee_review


@pytest.mark.integration
def test_e2e_mini_report_mocked():
    config = {
        "llm_provider": "openai",
        "deep_think_llm": "gpt-4o-mini",
        "quick_think_llm": "gpt-4o-mini",
        "postgres_url": "postgresql+psycopg://localhost/test_skip",
        "equity_research_use_memory": True,
        "equity_research": {
            "max_research_iterations": 1,
            "max_hypothesis_iterations": 1,
            "max_hypotheses_per_section": 2,
            "max_recur_limit": 50,
            "budget": {"max_search_queries": 0, "max_extraction_docs": 0},
            "embedding_provider": "hash",
            "thesis_score_threshold": 0.3,
        },
    }

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = _mock_llm_response(
        '{"hypotheses": [{"hypothesis": "Growth thesis", "category": "Revenue Growth", '
        '"overall_score": 8, "recommended_next_action": "develop"}], '
        '"stage": "convergence", "skills_to_run": ["variant_view_discovery"]}'
    )

    with patch("tradingagents.equity_research.graph.equity_research_graph.create_llm_client") as mock_client:
        client_inst = MagicMock()
        client_inst.get_llm.return_value = mock_llm
        mock_client.return_value = client_inst
        with patch("tradingagents.equity_research.graph.equity_research_graph.init_db"):
            with patch("tradingagents.llm_clients.perplexity_client.PerplexityClient.search") as mock_search:
                mock_search.return_value = {
                    "answer": "NVDA is a leading AI chip company.",
                    "citations": ["https://example.com/nvda"],
                }
                with patch("tradingagents.agents.utils.agent_utils.resolve_instrument_identity") as mock_id:
                    mock_id.return_value = {"name": "NVIDIA", "sector": "Technology", "industry": "Semiconductors"}
                    with patch("yfinance.Ticker") as mock_yf:
                        mock_yf.return_value.info = {"currentPrice": 100.0, "currency": "USD"}
                        with patch(
                            "tradingagents.equity_research.graph.setup.create_investment_committee_review",
                            _ic_always_pass,
                        ):
                            graph = EquityResearchGraph(config=config, init_database=False)
                            graph.deps.quick_llm = mock_llm
                            graph.deps.deep_llm = mock_llm
                            graph.deps.perplexity = MagicMock(
                                api_key="test",
                                search=MagicMock(return_value={
                                    "answer": "NVDA consensus buy rated",
                                    "citations": ["https://example.com"],
                                }),
                            )
                            graph.deps.redis = MagicMock()
                            graph.deps.redis.budget_get.return_value = 0
                            graph.deps.edgar = MagicMock()
                            graph.deps.edgar.fetch_recent_filings.return_value = []
                            graph.deps.fmp = MagicMock(available=False)
                            final_state, _ = graph.propagate("NVDA")

    assert final_state.get("final_report")
    assert final_state.get("research_graph") is not None
    assert final_state.get("research_traces")
