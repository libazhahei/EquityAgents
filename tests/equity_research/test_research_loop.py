"""Tests for research loop runtime."""

from unittest.mock import MagicMock, patch

from tradingagents.equity_research.agents.research_loop import create_research_loop
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


def test_research_loop_delegates_to_section_subgraph():
    deps = MagicMock()
    deps.trace = lambda state, *args, **kwargs: {}

    mock_updates = {
        "research_status": "continue",
        "research_iterations": 1,
        "section_research_outputs": {"3_business_model": {"section_id": "3_business_model"}},
        "research_plan": {"tasks": [{"task_id": "t_q1"}]},
        "answer_cards": {},
    }

    with patch(
        "tradingagents.equity_research.agents.research_loop.subgraph.create_run_section_research_subgraph",
    ) as mock_factory:
        mock_factory.return_value = lambda state: mock_updates
        loop = create_research_loop(deps)
        state = empty_equity_research_state()
        state["ticker"] = "TEST"
        state["section_plans"] = {
            "3_business_model": {"root_question": "q", "nodes": []},
        }
        result = loop(state)

    assert result["research_iterations"] == 1
    assert "research_status" in result
    assert "section_research_outputs" in result
