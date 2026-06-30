"""Tests for visualize_planner_trace script."""

from scripts.visualize_planner_trace import (
    _section_plans,
    build_question_tree_mermaid,
    build_section_overview_mermaid,
    render_html,
)


def _sample_plan(section_id: str = "4_industry_and_competition") -> dict:
    return {
        "section_id": section_id,
        "section_title": "Industry Analysis",
        "planning_thesis": "Test thesis",
        "root_question": "Can NVDA sustain leadership?",
        "nodes": [
            {"id": "q0", "parent_id": None, "level": 0, "question": "Root?", "downstream_agent": "research"},
            {"id": "q1", "parent_id": "q0", "level": 1, "question": "TAM?", "expected_output": "tam_estimate"},
            {"id": "q2", "parent_id": "q0", "level": 1, "question": "Share?", "expected_output": "market_share_analysis"},
            {"id": "q3", "parent_id": "q0", "level": 1, "question": "Competition?", "expected_output": "competitor_comparison_table"},
        ],
        "coverage_map": {"tam_estimate": ["q1"], "market_share_analysis": ["q2"]},
        "execution_order": ["q1", "q2", "q3", "q0"],
        "data_quality_flags": ["needs verification"],
    }


def test_section_plans_from_subgraph_outputs():
    state = {
        "subgraph_outputs": {
            "section_planner": {
                "section_plans": {"4_industry_and_competition": _sample_plan()},
            },
        },
    }
    plans = _section_plans(state)
    assert "4_industry_and_competition" in plans


def test_build_question_tree_mermaid_has_edges():
    mermaid = build_question_tree_mermaid(_sample_plan())
    assert "q0" in mermaid
    assert "-->" in mermaid


def test_render_html_includes_section_blocks():
    state = {
        "ticker": "NVDA",
        "section_plans": {
            "4_industry_and_competition": _sample_plan(),
        },
        "planner_exploration_graph": {"nodes": {}, "branch_roots": {}},
        "research_traces": [{"node_name": "section_planner_finalize", "payload": {"section_id": "4_industry_and_competition"}}],
    }
    html = render_html(state)
    assert "NVDA Section Planner Visualization" in html
    assert "4_industry_and_competition" in html
    assert "Question tree" in html
    assert build_section_overview_mermaid(state).startswith("flowchart")
