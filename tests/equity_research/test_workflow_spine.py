"""Tests for equity research workflow spine (R&D-Agent v2)."""

from unittest.mock import MagicMock

from tradingagents.equity_research.graph.setup import EquityGraphSetup


def test_setup_graph_has_rd_agent_nodes():
    deps = MagicMock()
    setup = EquityGraphSetup(deps)
    graph = setup.setup_graph()
    node_names = set(graph.nodes.keys())
    expected = {
        "initialize_state",
        "analyze_research_task",
        "dynamic_planning",
        "research_loop",
        "modeling_workflow",
        "valuation_workflow",
        "branch_merge",
        "risk_mapping",
        "investment_committee_review",
        "write_investment_focus",
        "assemble_report",
        "final_qa",
        "export_report",
    }
    assert expected.issubset(node_names)
    assert "autonomous_research" not in node_names
    assert len(node_names) <= 16
