"""Tests for blackboard → research-todo materialization."""

from __future__ import annotations

from tradingagents.equity_research.tasks.section_research.blackboard_todos import (
    blackboard_todo_materialize_enabled,
    materialize_blackboard_todos,
)
from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchStep,
    ResearchTask,
    ResearchTodoItem,
    ResearchTodoList,
    SectionResearchPlan,
)


def _bb(entry_type: str, content: str, *, entry_id: str = "bb_1", confidence: float = 0.6) -> dict:
    return {
        "entry_id": entry_id,
        "entry_type": entry_type,
        "content": content,
        "confidence": confidence,
        "created_at_iteration": 2,
        "source_node": "reflector",
        "section_id": "3_business_model",
    }


def _state_with_idle_plan(**extra) -> dict:
    plan = SectionResearchPlan(
        plan_id="p1",
        section_id="3_business_model",
        tasks=[
            ResearchTask(
                task_id="t1",
                question_id="q1",
                status="done",
                steps=[
                    ResearchStep(step_id="s1", order=1, action="search", status="done"),
                ],
            )
        ],
        execution_order=["t1"],
    )
    base = {
        "section_id": "3_business_model",
        "research_plan": plan.model_dump(),
        "research_todo_list": ResearchTodoList(
            list_id="todo_3_business_model",
            section_id="3_business_model",
            items=[],
        ).model_dump(),
    }
    base.update(extra)
    return base


def _state_with_pending_plan() -> dict:
    plan = SectionResearchPlan(
        plan_id="p1",
        section_id="3_business_model",
        tasks=[
            ResearchTask(
                task_id="t1",
                question_id="q1",
                status="pending",
                steps=[
                    ResearchStep(step_id="s1", order=1, action="search", status="pending"),
                ],
            )
        ],
        execution_order=["t1"],
    )
    return {
        "section_id": "3_business_model",
        "research_plan": plan.model_dump(),
        "research_todo_list": ResearchTodoList(
            list_id="todo_3_business_model",
            section_id="3_business_model",
        ).model_dump(),
    }


class TestBlackboardTodoMaterializeFlag:
    def test_default_on(self):
        assert blackboard_todo_materialize_enabled(None) is True
        assert blackboard_todo_materialize_enabled({}) is True
        assert blackboard_todo_materialize_enabled({"equity_research": {}}) is True

    def test_explicit_off(self):
        assert blackboard_todo_materialize_enabled(
            {"equity_research": {"blackboard_todo_materialize": False}}
        ) is False


class TestMaterializeBlackboardTodos:
    def test_skips_when_plan_has_runnable_step(self):
        state = _state_with_pending_plan()
        entries = [
            _bb("contradiction", "Segment mix in 10-K disagrees with earnings call narrative."),
        ]
        assert materialize_blackboard_todos(state, entries, config={}) is None

    def test_materializes_when_plan_idle(self):
        state = _state_with_idle_plan()
        entries = [
            _bb(
                "contradiction",
                "Answer-card confidence vs evidence support mismatch on revenue mix.",
                entry_id="bb_c1",
                confidence=0.8,
            ),
            _bb(
                "methodology",
                "Critical gap: No dedicated margin driver analysis output is present.",
                entry_id="bb_m1",
                confidence=0.6,
            ),
            _bb(
                "finding",
                "Data quality: Primary filing tables were not attached to the evidence bundle.",
                entry_id="bb_f1",
            ),
        ]
        todo = materialize_blackboard_todos(state, entries, config={})
        assert todo is not None
        assert len(todo.items) == 2
        assert [i.source for i in todo.items] == ["reflector", "reflector"]
        assert todo.items[0].action == "verify"
        assert todo.items[0].priority == 90
        assert todo.items[0].blackboard_entry_id == "bb_c1"
        assert todo.items[1].action == "search"
        assert todo.items[1].priority == 80
        assert todo.items[1].blackboard_entry_id == "bb_m1"

    def test_skip_verify_maps_contradiction_to_search(self):
        state = _state_with_idle_plan()
        entries = [
            _bb("contradiction", "Filing guidance conflicts with management commentary on ASP."),
        ]
        todo = materialize_blackboard_todos(
            state,
            entries,
            config={"equity_research": {"skip_verify": True}},
        )
        assert todo is not None
        assert todo.items[0].action == "search"

    def test_filings_gap_maps_to_fetch_primary(self):
        state = _state_with_idle_plan()
        entries = [
            _bb(
                "methodology",
                "Critical gap: Latest 10-K segment tables not yet extracted for q1.",
                entry_id="bb_m2",
            ),
        ]
        todo = materialize_blackboard_todos(state, entries, config={})
        assert todo is not None
        assert todo.items[0].action == "fetch_primary"

    def test_cap_three(self):
        state = _state_with_idle_plan()
        entries = [
            _bb("contradiction", f"Contradiction detail number {i} needs resolution now.", entry_id=f"bb_c{i}")
            for i in range(5)
        ]
        todo = materialize_blackboard_todos(state, entries, config={})
        assert todo is not None
        assert len(todo.items) == 3

    def test_dedup_by_entry_id(self):
        existing = ResearchTodoList(
            list_id="todo_3_business_model",
            section_id="3_business_model",
            items=[
                ResearchTodoItem(
                    item_id="todo_existing",
                    title="Already tracking",
                    description="Already tracking this contradiction in the queue.",
                    status="pending",
                    source="reflector",
                    blackboard_entry_id="bb_c1",
                )
            ],
        )
        state = _state_with_idle_plan(research_todo_list=existing.model_dump())
        entries = [
            _bb(
                "contradiction",
                "Completely different wording but same entry id should skip.",
                entry_id="bb_c1",
            ),
        ]
        assert materialize_blackboard_todos(state, entries, config={}) is None

    def test_disabled_by_config(self):
        state = _state_with_idle_plan()
        entries = [
            _bb("methodology", "Critical gap: pricing model still missing from answer card."),
        ]
        assert (
            materialize_blackboard_todos(
                state,
                entries,
                config={"equity_research": {"blackboard_todo_materialize": False}},
            )
            is None
        )
