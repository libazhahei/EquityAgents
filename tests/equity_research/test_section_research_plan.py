"""Tests for section research plan building."""

from tradingagents.equity_research.tasks.section_research.planning import build_fallback_plan


def test_fallback_plan_has_steps():
    brief = {
        "questions": [
            {"id": "q1", "question": "What is segment revenue mix?", "level": 1, "priority": 1},
            {"id": "q2", "question": "Pricing model?", "level": 1, "priority": 2},
        ],
    }
    plan = build_fallback_plan(brief, section_id="3_business_model", max_tasks=2)
    assert len(plan.tasks) == 2
    assert plan.execution_order[0] == plan.tasks[0].task_id
    for task in plan.tasks:
        assert len(task.steps) >= 4
        actions = {s.action for s in task.steps}
        assert "synthesize" in actions
