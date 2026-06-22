"""Tests for research graph operations."""

from tradingagents.equity_research.state.research_graph import (
    init_research_graph_from_gaps,
    select_parent_thesis_nodes,
    update_research_graph,
)


def test_init_research_graph_from_gaps():
    gaps = [{"gap_id": "g1", "description": "margin expansion underestimated"}]
    graph = init_research_graph_from_gaps(gaps)
    assert "initial_consensus_gap" in graph["nodes"]
    assert len(graph["branches"]) >= 5


def test_select_parent_thesis_nodes():
    graph = init_research_graph_from_gaps([])
    graph = update_research_graph(
        graph,
        parents=["initial_consensus_gap"],
        thesis="Revenue upside",
        real_score=0.7,
        branch_id="revenue_upside_branch",
    )
    parents = select_parent_thesis_nodes(graph)
    assert len(parents) >= 1


def test_update_research_graph_best_node():
    graph = init_research_graph_from_gaps([])
    graph = update_research_graph(
        graph,
        parents=["initial_consensus_gap"],
        thesis="Strong thesis",
        real_score=0.8,
        branch_id="margin_expansion_branch",
    )
    assert graph["best_node_id"] is not None
    best = graph["nodes"][graph["best_node_id"]]
    assert best["real_score"] == 0.8
