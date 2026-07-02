"""Tests for section research seed and brief building."""

from tradingagents.equity_research.tasks.section_research.profile import SECTION_RESEARCH_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.schemas import ResearchBrief
from tradingagents.equity_research.tasks.section_research.seed import (
    build_research_brief,
    seed_section_research_state,
)


def test_build_research_brief_from_plan():
    plan = {
        "section_title": "Business Model",
        "planning_thesis": "Explain revenue drivers",
        "root_question": "How does the company make money?",
        "nodes": [{"id": "q1", "question": "Segment mix?", "level": 1, "priority": 1}],
        "data_quality_flags": ["pricing incomplete"],
    }
    brief = build_research_brief(
        ticker="NVDA",
        section_id="3_business_model",
        section_plan=plan,
        consensus_view={"ticker": "NVDA", "coverage_score": 0.8},
    )
    assert brief.section_id == "3_business_model"
    assert brief.root_question.startswith("How does")
    assert "revenue_model_explanation" in brief.coverage_outputs
    assert len(brief.questions) == 1


def test_seed_section_research_state():
    parent = {
        "ticker": "NVDA",
        "section_plans": {
            "3_business_model": {
                "section_title": "Business Model",
                "root_question": "How?",
                "nodes": [],
            },
        },
    }
    state = seed_section_research_state(
        parent,
        SECTION_RESEARCH_TASK_PROFILE,
        section_id="3_business_model",
    )
    assert state["section_id"] == "3_business_model"
    assert state["research_brief"]
    assert state["research_plan"]
    assert state["research_todo_list"]
    assert state["bfs_levels"] == []
    assert state["bfs_wave_index"] == 0
    assert state["task_profile"]["task_id"] == "section_research"
