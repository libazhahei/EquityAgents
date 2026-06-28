"""Tests for ConsensusDemoGraph."""

from unittest.mock import MagicMock

from tradingagents.equity_research.runtime.demo_graph import ConsensusDemoGraph


def _mock_deps():
    deps = MagicMock()
    deps.config = {"equity_research": {}}
    deps.trace.return_value = {}
    return deps


def test_consensus_demo_graph_compiles():
    deps = _mock_deps()
    graph = ConsensusDemoGraph(deps, ticker="NVDA", sector="Tech", max_iterations=2)
    compiled = graph.compile()
    assert compiled is not None


def test_consensus_demo_graph_has_expected_nodes():
    deps = _mock_deps()
    graph = ConsensusDemoGraph(deps, ticker="AAPL")
    built = graph.build()
    node_names = set(built.nodes.keys())
    assert "initialize_demo_state" in node_names
    assert "run_consensus_subgraph" in node_names
