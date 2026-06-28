"""Tests for ExplorationGraph chain mode."""

from tradingagents.equity_research.runtime.exploration_graph import ExplorationGraph, ExplorationNode


def test_exploration_graph_add_and_chain():
    graph = ExplorationGraph()
    n1 = graph.new_node(branch_id="main", iteration=1, coverage_score=0.3)
    n2 = graph.new_node(parent_id=n1.node_id, branch_id="main", iteration=2, coverage_score=0.6)
    n3 = graph.new_node(parent_id=n2.node_id, branch_id="main", iteration=3, coverage_score=0.8)

    chain = graph.to_chain()
    assert len(chain) == 3
    assert chain[0].node_id == n1.node_id
    assert chain[-1].node_id == n3.node_id


def test_exploration_graph_best_node():
    graph = ExplorationGraph()
    graph.new_node(branch_id="main", iteration=1, coverage_score=0.3)
    graph.new_node(branch_id="main", iteration=2, coverage_score=0.9)
    graph.new_node(branch_id="main", iteration=3, coverage_score=0.5)

    best = graph.best_node()
    assert best is not None
    assert best.coverage_score == 0.9


def test_exploration_graph_serialization_roundtrip():
    graph = ExplorationGraph()
    node = graph.new_node(
        branch_id="main",
        iteration=1,
        coverage_score=0.75,
        routing_decision="exit",
        structured_view_snapshot={"ticker": "NVDA"},
    )
    restored = ExplorationGraph.from_dict(graph.to_dict())
    assert node.node_id in restored.nodes
    assert restored.nodes[node.node_id].coverage_score == 0.75
    assert restored.select_parents("greedy") == [node.node_id]
