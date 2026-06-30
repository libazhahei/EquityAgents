"""Tests for visualize_consensus_trace script."""

from scripts.visualize_consensus_trace import (
    _assumption_map,
    _detect_phases,
    build_assumption_map_mermaid,
    build_process_mermaid,
    render_html,
)


def test_detect_phases_with_assumption_view():
    state = {"ticker": "NVDA", "consensus_view": {}, "assumption_view": {"assumption_map": []}}
    assert _detect_phases(state) == {"consensus", "assumption"}


def test_assumption_map_from_legacy_dict():
    state = {
        "consensus_assumptions": {
            "A1": "The market is implicitly assuming that demand is strong",
            "top_research_priorities": ["capex check"],
        },
    }
    items = _assumption_map(state)
    assert len(items) == 1
    assert items[0]["_legacy"] is True


def test_render_html_includes_assumption_sections():
    state = {
        "ticker": "NVDA",
        "consensus_view": {"ticker": "NVDA", "dimension_coverage": {}},
        "assumption_view": {
            "ticker": "NVDA",
            "assumption_map": [
                {
                    "id": "A1",
                    "statement": "The market is implicitly assuming that AI demand remains elevated",
                    "category": "demand_assumptions",
                    "falsification_tests": ["Capex guide down"],
                },
            ],
            "top_research_priorities": ["Hyperscaler capex check"],
        },
        "research_traces": [
            {"node_name": "consensus_planner", "payload": {"new_queries": 5}},
            {"node_name": "assumption_planner", "payload": {"new_queries": 3}},
        ],
    }
    html = render_html(state)
    assert "Assumption map" in html
    assert "A1" in html
    assert "assumption_planner" in build_process_mermaid(state)
