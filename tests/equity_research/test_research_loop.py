"""Tests for research loop runtime."""

from unittest.mock import MagicMock

from tradingagents.equity_research.agents.research_loop import ResearchLoopRuntime
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.equity_research.state.research_graph import empty_research_graph


def test_research_loop_updates_graph_and_status():
    deps = MagicMock()
    deps.trace = lambda state, *args, **kwargs: {}
    deps.config = {"equity_research": {"thesis_score_threshold": 0.9, "max_hypotheses_per_section": 5}}
    deps.quick_llm.invoke.return_value = MagicMock(
        content='{"hypotheses": [{"hypothesis": "test thesis", "category": "Revenue Growth", '
        '"overall_score": 7, "recommended_next_action": "develop"}]}'
    )
    deps.deep_llm.invoke.return_value = MagicMock(
        content='{"hypotheses": [{"hypothesis": "test thesis", "category": "Revenue Growth", '
        '"overall_score": 7, "recommended_next_action": "develop"}]}'
    )
    deps.redis.budget_get.return_value = 0
    deps.perplexity.api_key = ""
    deps.edgar.fetch_recent_filings.return_value = []

    runtime = ResearchLoopRuntime(deps)
    state = empty_equity_research_state()
    state["ticker"] = "TEST"
    state["report_id"] = "r1"
    state["research_graph"] = empty_research_graph()
    state["research_plan"] = {
        "core_questions": [{
            "id": "Q1",
            "question": "variant_view discovery",
            "required_skills": ["variant_view_discovery"],
        }]
    }
    state["expectation_gaps"] = [{"gap_id": "g1", "description": "gap", "category": "consensus_gap"}]

    result = runtime.run(state)
    assert "research_status" in result
    assert result["research_iterations"] == 1
    assert "research_graph" in result
    assert len(result["research_graph"].get("nodes", {})) >= 1
