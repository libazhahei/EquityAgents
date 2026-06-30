"""Aggregate section plans for outer equity research state."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.runtime.exploration_graph import ExplorationGraph
from tradingagents.equity_research.state.ledgers import ResearchPlan, ResearchPlanQuestion
from tradingagents.equity_research.templates.report_template import MVP1_SECTION_ORDER


def planner_section_ids(*, include_investment_summary: bool = False) -> list[str]:
    skip = set() if include_investment_summary else {"1_investment_summary"}
    return [sid for sid in MVP1_SECTION_ORDER if sid not in skip]


def merge_exploration_graph(target: ExplorationGraph, section_result: dict[str, Any]) -> None:
    section_graph = ExplorationGraph.from_dict(section_result.get("exploration_graph"))
    for node in section_graph.nodes.values():
        target.nodes[node.node_id] = node
    target._branch_roots.update(section_graph._branch_roots)


def aggregate_research_plan(section_plans: dict[str, dict[str, Any]]) -> dict[str, Any]:
    questions: list[ResearchPlanQuestion] = []
    qnum = 1
    for section_id in planner_section_ids(include_investment_summary=True):
        plan = section_plans.get(section_id)
        if not plan:
            continue
        root = str(plan.get("root_question", "")).strip()
        if root:
            questions.append(ResearchPlanQuestion(
                id=f"Q{qnum}",
                question=root,
                priority="high",
                linked_sections=[section_id],
                required_skills=[],
            ))
            qnum += 1
        for node in plan.get("nodes", []):
            if int(node.get("level", 0)) != 1:
                continue
            question = str(node.get("question", "")).strip()
            if not question:
                continue
            questions.append(ResearchPlanQuestion(
                id=f"Q{qnum}",
                question=question,
                priority="medium",
                linked_sections=[section_id],
                required_skills=[],
            ))
            qnum += 1
            if qnum > 30:
                break
    return ResearchPlan(core_questions=questions).model_dump()


def derive_strategy_shim(state: dict[str, Any], section_plans: dict[str, dict[str, Any]]) -> dict[str, Any]:
    iterations = int(state.get("research_iterations", 0))
    max_iter = int(state.get("max_research_iterations", 5))
    if iterations < max_iter * 0.3:
        stage = "orientation"
    elif iterations < max_iter * 0.6:
        stage = "thesis_discovery"
    elif iterations < max_iter * 0.85:
        stage = "diligence_modeling"
    else:
        stage = "convergence"

    priority_questions: list[str] = []
    for section_id in planner_section_ids():
        plan = section_plans.get(section_id, {})
        nodes_by_id = {n.get("id"): n for n in plan.get("nodes", [])}
        for qid in plan.get("execution_order", []):
            node = nodes_by_id.get(qid, {})
            question = str(node.get("question", "")).strip()
            if question:
                priority_questions.append(question)
            if len(priority_questions) >= 3:
                break
        if len(priority_questions) >= 3:
            break

    return {
        "stage": stage,
        "exploration_vs_exploitation": "explore" if stage in ("orientation", "thesis_discovery") else "exploit",
        "priority_questions": priority_questions[:3],
        "skills_to_run": ["variant_view_discovery", "business_model_analysis"],
        "budget_allocation": {"evidence_search": 40, "financial_modeling": 20, "valuation": 10},
        "avoid_actions": ["premature_rating"] if stage != "convergence" else [],
        "reason": f"section_planner_shim stage={stage}",
    }
