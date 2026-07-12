"""Tests for equity research workflow spine (research MVP)."""

from unittest.mock import MagicMock

from tradingagents.equity_research.graph.setup import EquityGraphSetup


def test_setup_graph_has_research_spine_nodes():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.progress_bus = None
    setup = EquityGraphSetup(deps)
    graph = setup.setup_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "initialize_state",
        "consensus",
        "assumption",
        "human_review_1",
        "planner",
        "human_review_2",
        "pick_next_section",
        "section_research",
    }
    assert expected == node_names
    assert "analyze_research_task" not in node_names
    assert "modeling_workflow" not in node_names
    assert "autonomous_research" not in node_names
