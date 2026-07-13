"""Tests for section research bugfixes: wave tasks, articles, compact guard, reflector."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from tradingagents.equity_research.runtime.nodes.section_reflector import (
    _increment_question_iterations,
)
from tradingagents.equity_research.runtime.utils.context_compact import (
    clear_compact_cache,
    compact_if_needed,
)
from tradingagents.equity_research.tasks.section_research.articles import (
    merge_articles_and_refs,
    render_answer_card_article,
    write_question_article,
)
from tradingagents.equity_research.tasks.section_research.planning import (
    ensure_wave_tasks,
    expand_outline_to_plan,
    merge_plans,
    missing_wave_question_ids,
)
from tradingagents.equity_research.tasks.section_research.prompts import (
    build_initial_plan_prompt,
    build_wave_task_supplement_prompt,
)
from tradingagents.equity_research.tasks.section_research.schemas import (
    AnswerCard,
    PlannerTaskOutline,
    SectionResearchPlan,
    SectionResearchPlanOutlineLLMOutput,
)


def test_expand_outline_does_not_silently_fill_missing_wave_tasks():
    outline = SectionResearchPlanOutlineLLMOutput(
        plan_rationale="partial",
        tasks=[
            PlannerTaskOutline(
                task_id="t_q1",
                question_id="q1",
                objective="Q1",
                approach="search filings",
            ),
        ],
        execution_order=["t_q1"],
    )
    brief = {
        "questions": [
            {"id": "q1", "question": "Revenue?", "priority": 1},
            {"id": "q2", "question": "Pricing?", "priority": 2},
            {"id": "q3", "question": "Customers?", "priority": 3},
        ],
    }
    plan = expand_outline_to_plan(outline, brief, section_id="s3")
    assert {t.question_id for t in plan.tasks} == {"q1"}
    assert missing_wave_question_ids(plan, ["q1", "q2", "q3"]) == ["q2", "q3"]
    for task in plan.tasks:
        assert task.steps
        assert task.steps[0].action != "orient"


def test_merge_plans_adds_only_new_question_tasks():
    brief = {
        "questions": [
            {"id": "q1", "question": "Revenue?"},
            {"id": "q2", "question": "Pricing?"},
        ],
    }
    base = expand_outline_to_plan(
        SectionResearchPlanOutlineLLMOutput(
            tasks=[PlannerTaskOutline(task_id="t_q1", question_id="q1", objective="A", approach="s")],
            execution_order=["t_q1"],
        ),
        brief,
        section_id="s",
        plan_id="p1",
    )
    extra = expand_outline_to_plan(
        SectionResearchPlanOutlineLLMOutput(
            tasks=[
                PlannerTaskOutline(task_id="t_q1_dup", question_id="q1", objective="dup", approach="s"),
                PlannerTaskOutline(task_id="t_q2", question_id="q2", objective="B", approach="s"),
            ],
            execution_order=["t_q1_dup", "t_q2"],
        ),
        brief,
        section_id="s",
        plan_id="p1",
    )
    merged = merge_plans(base, extra)
    assert {t.question_id for t in merged.tasks} == {"q1", "q2"}
    assert len(merged.tasks) == 2


def test_initial_plan_prompt_lists_wave_checklist():
    deps = MagicMock()
    deps.config = {"equity_research": {"prompt_context_max_chars": 32000}}
    deps.nano_llm = MagicMock()
    state = {
        "ticker": "NVDA",
        "bfs_levels": [["q1", "q2"], ["q3"]],
        "bfs_wave_index": 0,
        "research_brief": {
            "section_id": "3_bm",
            "section_title": "Business Model",
            "root_question": "How does it make money?",
            "questions": [
                {"id": "q1", "question": "Revenue mix?", "priority": 1},
                {"id": "q2", "question": "Pricing?", "priority": 2},
                {"id": "q3", "question": "Later?", "priority": 3},
            ],
        },
    }
    prompt = build_initial_plan_prompt(deps, state)
    assert "question_id=`q1`" in prompt
    assert "question_id=`q2`" in prompt
    assert "exactly 2 tasks" in prompt
    assert "tasks.length MUST be 2" in prompt
    # Next-wave q3 must not be required in the mandatory checklist count
    checklist = prompt.split("CURRENT WAVE CHECKLIST")[1].split("Questions (from section planner)")[0]
    assert "`q1`" in checklist and "`q2`" in checklist
    assert "`q3`" not in checklist


def test_supplement_prompt_targets_missing_only():
    deps = MagicMock()
    deps.config = {"equity_research": {"prompt_context_max_chars": 32000}}
    deps.nano_llm = MagicMock()
    state = {
        "ticker": "NVDA",
        "research_brief": {
            "section_id": "3_bm",
            "section_title": "Business Model",
            "questions": [
                {"id": "q2", "question": "Pricing?", "priority": 2},
                {"id": "q3", "question": "Customers?", "priority": 3},
            ],
        },
    }
    prompt = build_wave_task_supplement_prompt(
        deps, state, missing_qids=["q2", "q3"], existing_task_qids=["q1"],
    )
    assert "exactly 2 tasks" in prompt
    assert "q2" in prompt and "q3" in prompt
    assert "Already covered" in prompt


def test_ensure_wave_tasks_idempotent():
    plan = SectionResearchPlan(
        plan_id="p1",
        section_id="s",
        tasks=[],
        execution_order=[],
    )
    brief = {"questions": [{"id": "q1", "question": "A?"}]}
    filled = ensure_wave_tasks(plan, ["q1"], brief)
    again = ensure_wave_tasks(filled, ["q1"], brief)
    assert len(again.tasks) == 1
    assert again.tasks[0].question_id == "q1"


def test_increment_only_active_question():
    state = {
        "question_iterations": {"q1": 1, "q2": 0},
        "active_task": {"question_id": "q1"},
        "research_plan": {
            "tasks": [
                {"question_id": "q1", "status": "in_progress", "steps": [{"status": "in_progress"}]},
                {"question_id": "q2", "status": "pending", "steps": [{"status": "pending"}]},
            ],
        },
    }
    updated = _increment_question_iterations(state)
    assert updated["q1"] == 2
    assert updated["q2"] == 0


def test_article_render_and_ref_merge(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))  # unused; we pass explicit dirs
    card = AnswerCard(
        question_id="q1",
        question="What is revenue mix?",
        short_answer="Data center is majority.",
        verified_facts=[{
            "metric": "data_center_pct",
            "value": 55,
            "unit": "%",
            "period": "FY2024",
            "url": "https://example.com/a",
        }],
        draft_paragraph="Data center mix rose to majority https://example.com/a",
        citations=[{"url": "https://example.com/a", "title": "10-K"}],
        open_gaps=["Need ASP"],
    )
    md, refs = render_answer_card_article(card)
    assert "## Short Answer" in md
    assert "## Key Facts" in md
    assert "[1]" in md
    assert refs["1"]["url"] == "https://example.com/a"

    art_dir = tmp_path / "articles"
    art_dir.mkdir()
    state = {
        "ticker": "NVDA",
        "section_id": "3_business_model",
        "section_artifact_dir": str(art_dir),
    }
    write_question_article(state, "q1", card, question_text="What is revenue mix?")
    card2 = AnswerCard(
        question_id="q2",
        question="Pricing?",
        short_answer="Premium ASP.",
        draft_paragraph="ASP is elevated [1]",
        citations=[{"url": "https://example.com/a", "title": "10-K"}, {"url": "https://example.com/b", "title": "IR"}],
        verified_facts=[],
        open_gaps=[],
    )
    write_question_article(state, "q2", card2, question_text="Pricing?")

    report, global_refs = merge_articles_and_refs(art_dir, executive_summary="NVDA mix remains DC-led.")
    assert "# Executive Summary" in report
    assert "NVDA mix remains DC-led." in report
    assert "# References" in report
    # Same URL deduped to one global number
    urls = {meta["url"] for meta in global_refs.values()}
    assert urls == {"https://example.com/a", "https://example.com/b"}
    assert len(global_refs) == 2


def test_compact_if_needed_hard_guard_avoids_huge_llm_input():
    clear_compact_cache()
    deps = MagicMock()
    deps.config = {
        "equity_research": {
            "prompt_context_max_chars": 100,
            "compact_llm_max_input_chars": 500,
        },
    }
    nano = MagicMock()
    nano.model_name = "nano-test"
    nano.invoke = MagicMock(return_value=MagicMock(content="compressed"))
    deps.nano_llm = nano

    huge = "HEADING\n" + ("body " * 200_000)
    result = compact_if_needed(deps, huge, purpose="unit-test-hard-guard")
    assert result
    assert nano.invoke.called
    prompt = nano.invoke.call_args[0][0]
    # Prompt must stay near the hard cap, never tens of MB
    assert len(prompt) < 6000
    assert "truncated" in prompt or len(prompt) <= 5500


def test_initial_planner_runs_llm_supplement_for_missing_wave_tasks(monkeypatch):
    from tradingagents.equity_research.runtime.nodes import section_planner as sp
    from tradingagents.equity_research.tasks.section_research.profile import (
        SECTION_RESEARCH_TASK_PROFILE,
    )

    calls: list[str] = []

    def fake_invoke(deps, llm, prompt, *, agent_name):
        calls.append(agent_name)
        if agent_name.endswith("_wave_supplement"):
            return SectionResearchPlanOutlineLLMOutput(
                plan_rationale="supplement",
                tasks=[
                    PlannerTaskOutline(
                        task_id="t_q2", question_id="q2", objective="Pricing", approach="search",
                    ),
                ],
                execution_order=["t_q2"],
            )
        return SectionResearchPlanOutlineLLMOutput(
            plan_rationale="partial",
            tasks=[
                PlannerTaskOutline(
                    task_id="t_q1", question_id="q1", objective="Revenue", approach="filings",
                ),
            ],
            execution_order=["t_q1"],
        )

    monkeypatch.setattr(sp, "_invoke_plan_outline", fake_invoke)

    deps = MagicMock()
    deps.config = {"equity_research": {"prompt_context_max_chars": 32000, "structured_output_max_retries": 1}}
    deps.deep_llm = MagicMock()
    deps.quick_llm = MagicMock()
    deps.nano_llm = MagicMock()
    deps.trace = MagicMock(side_effect=lambda *_a, **_k: {})

    state = {
        "ticker": "NVDA",
        "section_id": "3_bm",
        "bfs_levels": [["q1", "q2"]],
        "bfs_wave_index": 0,
        "research_brief": {
            "section_id": "3_bm",
            "section_title": "Business Model",
            "root_question": "root?",
            "questions": [
                {"id": "q1", "question": "Revenue?", "priority": 1},
                {"id": "q2", "question": "Pricing?", "priority": 2},
            ],
        },
        "question_graph": {"q1": [], "q2": []},
        "errors": [],
    }
    node = sp.create_section_planner_node(deps, SECTION_RESEARCH_TASK_PROFILE, mode="initial")
    updates = node(state)
    plan = updates["research_plan"]
    qids = {t["question_id"] for t in plan["tasks"]}
    assert qids == {"q1", "q2"}
    assert any(name.endswith("_wave_supplement") for name in calls)
