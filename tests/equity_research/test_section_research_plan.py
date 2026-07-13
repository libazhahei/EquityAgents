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
        assert len(task.steps) >= 3
        actions = {s.action for s in task.steps}
        assert "orient" not in actions
        assert "synthesize" in actions
        assert "verify" in actions
        assert task.success_criteria["require_structured_quant"] is True
        assert task.success_criteria["require_structured_sources"] is True
        assert task.success_criteria["require_data_availability_check"] is True


def test_fallback_plan_respects_wave_qids():
    brief = {
        "questions": [
            {"id": "q1", "question": "A?", "level": 1, "priority": 1},
            {"id": "q2", "question": "B?", "level": 1, "priority": 2},
            {"id": "q3", "question": "C?", "level": 2, "priority": 3},
        ],
    }
    plan = build_fallback_plan(
        brief, section_id="s", max_tasks=2, wave_qids=["q1", "q2", "q3"],
    )
    assert {t.question_id for t in plan.tasks} == {"q1", "q2", "q3"}
