"""Rule-based fallback plan builder when LLM planning is unavailable."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.tasks.section_research.schemas import (
    PlannerTaskOutline,
    ResearchStep,
    ResearchTask,
    SectionResearchPlan,
    SectionResearchPlanOutlineLLMOutput,
)

_ACTION_BY_KEYWORD: list[tuple[tuple[str, ...], str, list[str]]] = [
    (("revenue", "segment", "financial", "margin", "metric"), "fetch_primary", ["filings_search", "filing_reader"]),
    (("price", "pricing", "asp"), "search", ["web_search", "transcript_search"]),
    (("customer", "channel", "concentration"), "search", ["web_search", "filings_search"]),
    (("competition", "industry", "market"), "search", ["web_search", "news_search"]),
    (("ownership", "management", "governance"), "fetch_primary", ["filings_search", "filing_reader"]),
]


def _infer_action_and_tools(question: str, expected_output: str) -> tuple[str, list[str]]:
    text = f"{question} {expected_output}".lower()
    for keywords, action, tools in _ACTION_BY_KEYWORD:
        if any(k in text for k in keywords):
            return action, list(tools)
    return "search", ["web_search", "batch_light_grounding_search"]


def _default_steps_for_question(
    question: dict[str, Any],
    *,
    priority: int,
) -> list[ResearchStep]:
    del priority  # reserved for future priority-aware step templates
    qtext = str(question.get("question", ""))
    expected = str(question.get("expected_output", ""))
    action, tools = _infer_action_and_tools(qtext, expected)
    qid = str(question.get("id", "q"))
    steps: list[ResearchStep] = []
    if action == "fetch_primary":
        steps.extend([
            ResearchStep(
                step_id=f"{qid}_s1",
                order=1,
                action="fetch_primary",
                description="Fetch latest primary filings (10-K, 10-Q, earnings materials)",
                tool_hints=["filings_search", "filing_reader", "financial_statement_fetch", "memory_retrieve"],
                expected_output="Primary source documents",
            ),
            ResearchStep(
                step_id=f"{qid}_s2",
                order=2,
                action="extract",
                description=f"Extract data for: {expected[:100] or qtext[:100]}",
                tool_hints=["table_extractor", "reference_parser"],
                inputs_from=[f"{qid}_s1"],
                expected_output=expected or "Extracted metrics with citations",
            ),
        ])
    else:
        steps.append(
            ResearchStep(
                step_id=f"{qid}_s1",
                order=1,
                action="search",
                description=f"Search evidence for: {qtext[:120]}",
                tool_hints=[*tools, "memory_retrieve"],
                expected_output=expected or "Relevant evidence snippets",
            ),
        )
    calc_order = len(steps) + 1
    steps.append(
        ResearchStep(
            step_id=f"{qid}_s{calc_order}",
            order=calc_order,
            action="calculate",
            description="Compute derived metrics if applicable",
            tool_hints=["calculator"],
            inputs_from=[steps[-1].step_id],
            expected_output="Calculations with formulas",
        ),
    )
    syn_order = calc_order + 1
    steps.append(
        ResearchStep(
            step_id=f"{qid}_s{syn_order}",
            order=syn_order,
            action="synthesize",
            description=f"Write answer card for {qid}",
            tool_hints=["store_evidence", "memory_write"],
            inputs_from=[steps[-1].step_id],
            expected_output="Answer card with citations",
        ),
    )
    verify_order = syn_order + 1
    steps.append(
        ResearchStep(
            step_id=f"{qid}_s{verify_order}",
            order=verify_order,
            action="verify",
            description="Verify metric availability and capture source metadata completeness",
            tool_hints=["reference_parser", "citation_checker", "claim_evidence_checker"],
            inputs_from=[steps[-1].step_id],
            expected_output="Availability verdict + source metadata fields + unresolved gaps",
        ),
    )
    return steps


def _compact_steps_for_outline(
    qid: str,
    objective: str,
    approach: str,
    question: dict[str, Any] | None = None,
) -> list[ResearchStep]:
    q = question or {}
    expected = str(q.get("expected_output", ""))
    action, tools = _infer_action_and_tools(f"{objective} {approach}", expected)
    mid_description = approach or objective
    steps: list[ResearchStep] = []
    if action == "fetch_primary":
        steps.append(
            ResearchStep(
                step_id=f"{qid}_s1",
                order=1,
                action="fetch_primary",
                description=mid_description,
                tool_hints=["filings_search", "filing_reader", "financial_statement_fetch", "memory_retrieve"],
                expected_output="Primary source documents",
            ),
        )
    else:
        steps.append(
            ResearchStep(
                step_id=f"{qid}_s1",
                order=1,
                action="search",
                description=mid_description,
                tool_hints=[*tools, "memory_retrieve"],
                expected_output=expected or "Relevant evidence snippets",
            ),
        )
    steps.append(
        ResearchStep(
            step_id=f"{qid}_s2",
            order=2,
            action="synthesize",
            description=f"Synthesize answer for {qid}",
            tool_hints=["store_evidence", "memory_write"],
            inputs_from=[f"{qid}_s1"],
            expected_output="Answer card with citations",
        ),
    )
    steps.append(
        ResearchStep(
            step_id=f"{qid}_s3",
            order=3,
            action="verify",
            description=f"Verify data availability and source metadata completeness for {qid}",
            tool_hints=["reference_parser", "citation_checker", "claim_evidence_checker"],
            inputs_from=[f"{qid}_s2"],
            expected_output="Availability note and source metadata completeness check",
        ),
    )
    return steps


def _default_success_criteria() -> dict[str, Any]:
    return {
        "confidence_threshold": 0.7,
        "min_primary_sources": 1,
        "require_structured_quant": True,
        "require_structured_sources": True,
        "require_data_availability_check": True,
    }


def _task_from_question(q: dict[str, Any], *, objective: str = "", approach: str = "") -> ResearchTask:
    qid = str(q.get("id", f"q_{uuid.uuid4().hex[:4]}"))
    priority = max(50, 100 - int(q.get("priority", 5)) * 5)
    obj = objective or str(q.get("question", ""))
    task_id = f"t_{qid}"
    if approach:
        steps = _compact_steps_for_outline(qid, obj, approach, q)
    else:
        steps = _default_steps_for_question(q, priority=priority)
    return ResearchTask(
        task_id=task_id,
        question_id=qid,
        objective=obj,
        task_type=str(q.get("downstream_agent") or "evidence_search"),
        priority=priority,
        steps=steps,
        required_sources=list(q.get("suggested_sources") or q.get("required_evidence") or []),
        expected_artifacts=[str(q.get("expected_output", ""))],
        success_criteria=_default_success_criteria(),
    )


def missing_wave_question_ids(
    plan: SectionResearchPlan,
    wave_qids: list[str],
) -> list[str]:
    """Return wave question_ids that still lack a task."""
    covered = {t.question_id for t in plan.tasks}
    return [qid for qid in wave_qids if qid not in covered]


def merge_plans(
    base: SectionResearchPlan,
    extra: SectionResearchPlan,
) -> SectionResearchPlan:
    """Append tasks from extra that introduce new question_ids / task_ids."""
    seen_qids = {t.question_id for t in base.tasks}
    seen_tids = {t.task_id for t in base.tasks}
    tasks = list(base.tasks)
    execution_order = list(base.execution_order)
    for task in extra.tasks:
        if task.question_id in seen_qids or task.task_id in seen_tids:
            continue
        tasks.append(task)
        execution_order.append(task.task_id)
        seen_qids.add(task.question_id)
        seen_tids.add(task.task_id)
    rationale = base.plan_rationale
    if extra.plan_rationale:
        rationale = f"{rationale}\n[supplement] {extra.plan_rationale}".strip()
    return SectionResearchPlan(
        plan_id=base.plan_id,
        section_id=base.section_id,
        version=base.version,
        tasks=tasks,
        execution_order=execution_order,
        plan_rationale=rationale,
        plan_history=list(base.plan_history),
    )


def ensure_wave_tasks(
    plan: SectionResearchPlan,
    wave_qids: list[str],
    brief: dict[str, Any],
) -> SectionResearchPlan:
    """Deprecated deterministic fill — prefer LLM supplement round.

    Kept for tests / emergency last resort only.
    """
    if not wave_qids:
        return plan
    questions_by_id = {str(q.get("id", "")): q for q in (brief.get("questions") or [])}
    covered = {t.question_id for t in plan.tasks}
    tasks = list(plan.tasks)
    execution_order = list(plan.execution_order)
    for qid in wave_qids:
        if qid in covered:
            continue
        q = questions_by_id.get(qid) or {
            "id": qid,
            "question": qid,
            "priority": 5,
            "expected_output": "Section research answer with citations",
        }
        task = _task_from_question(q)
        tasks.append(task)
        execution_order.append(task.task_id)
        covered.add(qid)
    if len(tasks) == len(plan.tasks):
        return plan
    return SectionResearchPlan(
        plan_id=plan.plan_id,
        section_id=plan.section_id,
        version=plan.version,
        tasks=tasks,
        execution_order=execution_order,
        plan_rationale=plan.plan_rationale,
        plan_history=list(plan.plan_history),
    )


def expand_outline_to_plan(
    outline: SectionResearchPlanOutlineLLMOutput,
    brief: dict[str, Any],
    *,
    section_id: str,
    plan_id: str | None = None,
    wave_qids: list[str] | None = None,
) -> SectionResearchPlan:
    del wave_qids  # coverage is enforced via LLM supplement in the planner node
    questions_by_id = {str(q.get("id", "")): q for q in (brief.get("questions") or [])}
    tasks: list[ResearchTask] = []
    execution_order = list(outline.execution_order) or [t.task_id for t in outline.tasks]
    order_set = set(execution_order)
    for outline_task in outline.tasks:
        if outline_task.task_id not in order_set:
            execution_order.append(outline_task.task_id)
            order_set.add(outline_task.task_id)
        q = questions_by_id.get(outline_task.question_id, {})
        priority = max(50, 100 - int(q.get("priority", 5)) * 5)
        objective = outline_task.objective or str(q.get("question", ""))
        tasks.append(
            ResearchTask(
                task_id=outline_task.task_id,
                question_id=outline_task.question_id,
                objective=objective,
                task_type=str(q.get("downstream_agent") or "evidence_search"),
                priority=priority,
                steps=_compact_steps_for_outline(
                    outline_task.question_id,
                    objective,
                    outline_task.approach,
                    q,
                ),
                required_sources=list(q.get("suggested_sources") or q.get("required_evidence") or []),
                expected_artifacts=[str(q.get("expected_output", ""))],
                success_criteria=_default_success_criteria(),
            ),
        )
    return SectionResearchPlan(
        plan_id=plan_id or f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
        section_id=section_id,
        tasks=tasks,
        execution_order=execution_order,
        plan_rationale=outline.plan_rationale,
    )


def expand_task_outlines(
    outlines: list[PlannerTaskOutline],
    brief: dict[str, Any],
) -> list[ResearchTask]:
    questions_by_id = {str(q.get("id", "")): q for q in (brief.get("questions") or [])}
    tasks: list[ResearchTask] = []
    for outline_task in outlines:
        q = questions_by_id.get(outline_task.question_id, {})
        priority = max(50, 100 - int(q.get("priority", 5)) * 5)
        objective = outline_task.objective or str(q.get("question", ""))
        tasks.append(
            ResearchTask(
                task_id=outline_task.task_id,
                question_id=outline_task.question_id,
                objective=objective,
                task_type=str(q.get("downstream_agent") or "evidence_search"),
                priority=priority,
                steps=_compact_steps_for_outline(
                    outline_task.question_id,
                    objective,
                    outline_task.approach,
                    q,
                ),
                required_sources=list(q.get("suggested_sources") or q.get("required_evidence") or []),
                expected_artifacts=[str(q.get("expected_output", ""))],
                success_criteria=_default_success_criteria(),
            ),
        )
    return tasks


def build_fallback_plan(
    brief: dict[str, Any],
    *,
    section_id: str,
    max_tasks: int = 8,
    wave_qids: list[str] | None = None,
) -> SectionResearchPlan:
    questions = list(brief.get("questions") or [])
    questions_by_id = {str(q.get("id", "")): q for q in questions}
    if wave_qids:
        level_1 = [questions_by_id[qid] for qid in wave_qids if qid in questions_by_id]
        for qid in wave_qids:
            if qid not in questions_by_id:
                level_1.append({
                    "id": qid,
                    "question": qid,
                    "level": 1,
                    "priority": 5,
                    "expected_output": "Section research answer with citations",
                })
        max_tasks = max(max_tasks, len(level_1))
    else:
        level_1 = [q for q in questions if int(q.get("level", 0)) >= 1]
        if not level_1 and questions:
            level_1 = questions[:max_tasks]
    if not level_1:
        root_q = str(brief.get("root_question") or brief.get("section_title") or section_id)
        level_1 = [{
            "id": "q_root",
            "question": root_q,
            "level": 1,
            "priority": 1,
            "expected_output": "Section research answer with citations",
        }]
    level_1.sort(key=lambda q: int(q.get("priority", 99)))
    tasks: list[ResearchTask] = []
    execution_order: list[str] = []
    for q in level_1[:max_tasks]:
        task = _task_from_question(q)
        tasks.append(task)
        execution_order.append(task.task_id)
    plan = SectionResearchPlan(
        plan_id=f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
        section_id=section_id,
        tasks=tasks,
        execution_order=execution_order,
        plan_rationale="Rule-based plan from question tree (LLM fallback).",
    )
    if wave_qids:
        plan = ensure_wave_tasks(plan, wave_qids, brief)
    return plan
