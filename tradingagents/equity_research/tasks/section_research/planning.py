"""Rule-based fallback plan builder when LLM planning is unavailable."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchStep,
    ResearchTask,
    SectionResearchPlan,
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
    qtext = str(question.get("question", ""))
    expected = str(question.get("expected_output", ""))
    action, tools = _infer_action_and_tools(qtext, expected)
    qid = str(question.get("id", "q"))
    steps = [
        ResearchStep(
            step_id=f"{qid}_s1",
            order=1,
            action="orient",
            description=f"Review context and plan evidence for: {qtext[:120]}",
            tool_hints=["memory_retrieve", "list_research_todos"],
            expected_output="Clear evidence plan",
        ),
    ]
    if action == "fetch_primary":
        steps.extend([
            ResearchStep(
                step_id=f"{qid}_s2",
                order=2,
                action="fetch_primary",
                description="Fetch latest primary filings (10-K, 10-Q, earnings materials)",
                tool_hints=["filings_search", "filing_reader", "financial_statement_fetch"],
                inputs_from=[f"{qid}_s1"],
                expected_output="Primary source documents",
            ),
            ResearchStep(
                step_id=f"{qid}_s3",
                order=3,
                action="extract",
                description=f"Extract data for: {expected[:100] or qtext[:100]}",
                tool_hints=["table_extractor", "reference_parser"],
                inputs_from=[f"{qid}_s2"],
                expected_output=expected or "Extracted metrics with citations",
            ),
        ])
    else:
        steps.append(
            ResearchStep(
                step_id=f"{qid}_s2",
                order=2,
                action="search",
                description=f"Search evidence for: {qtext[:120]}",
                tool_hints=tools,
                inputs_from=[f"{qid}_s1"],
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
    return steps


def build_fallback_plan(
    brief: dict[str, Any],
    *,
    section_id: str,
    max_tasks: int = 8,
) -> SectionResearchPlan:
    questions = list(brief.get("questions") or [])
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
        qid = str(q.get("id", f"q_{uuid.uuid4().hex[:4]}"))
        priority = max(50, 100 - int(q.get("priority", 5)) * 5)
        task_id = f"t_{qid}"
        tasks.append(
            ResearchTask(
                task_id=task_id,
                question_id=qid,
                objective=str(q.get("question", "")),
                task_type=str(q.get("downstream_agent") or "evidence_search"),
                priority=priority,
                steps=_default_steps_for_question(q, priority=priority),
                required_sources=list(q.get("suggested_sources") or q.get("required_evidence") or []),
                expected_artifacts=[str(q.get("expected_output", ""))],
                success_criteria={"confidence_threshold": 0.7, "min_primary_sources": 1},
            ),
        )
        execution_order.append(task_id)
    return SectionResearchPlan(
        plan_id=f"plan_{section_id}_{uuid.uuid4().hex[:6]}",
        section_id=section_id,
        tasks=tasks,
        execution_order=execution_order,
        plan_rationale="Rule-based plan from question tree (LLM fallback).",
    )
