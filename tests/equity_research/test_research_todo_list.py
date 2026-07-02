"""Tests for research todo list CRUD and plan sync."""

from tradingagents.equity_research.tasks.section_research.planning import build_fallback_plan
from tradingagents.equity_research.tasks.section_research.todo_sync import plan_to_todo_sync
from tradingagents.equity_research.tools import todo_tools


def test_plan_to_todo_sync():
    brief = {
        "questions": [
            {"id": "q1", "question": "Segment revenue?", "level": 1, "priority": 1, "expected_output": "table"},
        ],
    }
    plan = build_fallback_plan(brief, section_id="3_business_model", max_tasks=1)
    todo = plan_to_todo_sync(plan)
    assert todo.section_id == "3_business_model"
    assert len(todo.items) >= 3
    assert todo.items[0].task_id == plan.tasks[0].task_id
    assert todo.items[0].step_id


def test_todo_crud():
    state = {
        "section_id": "3_business_model",
        "research_todo_list": {
            "list_id": "todo_3",
            "section_id": "3_business_model",
            "version": 1,
            "items": [],
        },
    }
    added = todo_tools.add_research_todo(
        state, title="Fetch 10-K", question_id="q1", action="fetch_primary", priority=90,
    )
    assert added["added_item"]["title"] == "Fetch 10-K"
    state["research_todo_list"] = added["research_todo_list"]

    listed = todo_tools.list_research_todos(state, status="pending")
    assert listed["total"] == 1

    item_id = listed["items"][0]["item_id"]
    removed = todo_tools.remove_research_todo(state, item_id)
    items = removed["research_todo_list"]["items"]
    assert items[0]["status"] == "cancelled"
