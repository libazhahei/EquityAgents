"""Tests for BFS wave todo expansion."""

from tradingagents.equity_research.tasks.section_research.bfs_todos import (
    append_wave_todos,
    bfs_levels,
    has_next_bfs_wave,
    tasks_for_wave,
    wave_complete,
)
from tradingagents.equity_research.tasks.section_research.planning import build_fallback_plan


def test_bfs_levels_from_question_graph():
    graph = {
        "nodes": {
            "root": {"id": "root", "level": 0, "parent_id": None},
            "q1": {"id": "q1", "level": 1, "parent_id": "root", "priority": 1},
            "q2": {"id": "q2", "level": 1, "parent_id": "root", "priority": 2},
            "q1a": {"id": "q1a", "level": 2, "parent_id": "q1", "priority": 1},
        },
    }
    levels = bfs_levels(graph)
    assert levels[0] == ["q1", "q2"]
    assert levels[1] == ["q1a"]


def test_append_wave_todos_only_current_wave():
    brief = {
        "questions": [
            {"id": "q1", "question": "Q1?", "level": 1, "priority": 1},
            {"id": "q2", "question": "Q2?", "level": 1, "priority": 2},
        ],
    }
    plan = build_fallback_plan(brief, section_id="3_business_model", max_tasks=2)
    todo = append_wave_todos(plan, ["q1"], None, wave_index=0)
    qids = {item.question_id for item in todo.items}
    assert qids == {"q1"}
    assert len(todo.items) >= 3


def test_wave_complete_and_next_wave():
    brief = {
        "questions": [
            {"id": "q1", "question": "Q1?", "level": 1, "priority": 1},
            {"id": "q1a", "question": "Q1a?", "level": 2, "parent_id": "q1", "priority": 1},
        ],
        "root_question": "Root?",
    }
    plan = build_fallback_plan(brief, section_id="3_business_model", max_tasks=2)
    graph = {
        "nodes": {
            "root": {"id": "root", "level": 0},
            "q1": {"id": "q1", "level": 1, "parent_id": "root"},
            "q1a": {"id": "q1a", "level": 2, "parent_id": "q1"},
        },
    }
    levels = bfs_levels(graph)
    assert levels == [["q1"], ["q1a"]]
    state = {
        "bfs_levels": levels,
        "bfs_wave_index": 0,
        "research_plan": plan.model_dump(),
        "question_graph": graph,
    }
    assert not wave_complete(state)
    for task in plan.tasks:
        if task.question_id != "q1":
            continue
        task.status = "done"
        for step in task.steps:
            step.status = "done"
    state["research_plan"] = plan.model_dump()
    assert wave_complete(state)
    assert has_next_bfs_wave(state)


def test_build_fallback_plan_from_root_when_no_questions():
    brief = {
        "questions": [],
        "root_question": "How does NVDA make money?",
        "section_title": "Business Model",
    }
    plan = build_fallback_plan(brief, section_id="3_business_model")
    assert len(plan.tasks) == 1
    assert plan.tasks[0].question_id == "q_root"
    wave_tasks = tasks_for_wave(plan, ["q_root"])
    assert len(wave_tasks) == 1
