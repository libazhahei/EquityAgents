"""Normalize and validate section research plans."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.tasks.section_planner.schemas import (
    ResearchQuestionNode,
    SectionPlannerRequest,
    SectionResearchPlan,
)


def normalize_plan_dict(data: dict[str, Any], req: SectionPlannerRequest) -> dict[str, Any]:
    data.setdefault("ticker", req.ticker)
    data.setdefault("section_id", req.section_id)
    data.setdefault("section_title", req.section_title)
    data.setdefault("planning_thesis", "")
    data.setdefault("root_question", "")
    data.setdefault("nodes", [])
    data.setdefault("coverage_map", {})
    data.setdefault("execution_order", [])
    data.setdefault("data_quality_flags", [])
    data.setdefault("planner_notes", None)

    if not isinstance(data["nodes"], list):
        data["nodes"] = []

    if not data["nodes"]:
        root_id = "q0"
        root_question = data.get("root_question") or (
            f"What must be researched to complete {req.section_title} for {req.ticker}?"
        )
        data["root_question"] = root_question
        data["nodes"] = [
            {
                "id": root_id,
                "parent_id": None,
                "level": 0,
                "question": root_question,
                "rationale": "Auto-filled root node because planner returned no valid nodes.",
                "priority": 1,
                "required_evidence": list(req.required_outputs),
                "suggested_sources": [],
                "expected_output": req.section_title,
                "downstream_agent": None,
                "stop_condition_hint": None,
            }
        ]

    if not data.get("root_question"):
        data["root_question"] = data["nodes"][0].get("question", "")

    seen: set[str] = set()
    root_id = data["nodes"][0].get("id", "q0")

    for i, node in enumerate(data["nodes"]):
        if not isinstance(node, dict):
            node = {}
            data["nodes"][i] = node

        node.setdefault("id", f"q{i}")

        if node["id"] in seen:
            node["id"] = f"{node['id']}_{uuid.uuid4().hex[:4]}"

        seen.add(node["id"])
        node.setdefault("parent_id", None if i == 0 else root_id)
        node.setdefault("level", 0 if i == 0 else 1)
        node.setdefault("question", "")
        node.setdefault("rationale", "")
        node.setdefault("priority", i + 1)
        node.setdefault("required_evidence", [])
        node.setdefault("suggested_sources", [])
        node.setdefault("expected_output", "")
        node.setdefault("downstream_agent", None)
        node.setdefault("stop_condition_hint", None)

        if not isinstance(node["required_evidence"], list):
            node["required_evidence"] = [str(node["required_evidence"])]
        if not isinstance(node["suggested_sources"], list):
            node["suggested_sources"] = [str(node["suggested_sources"])]

    node_ids = {n["id"] for n in data["nodes"]}

    if not data["execution_order"]:
        data["execution_order"] = [
            n["id"]
            for n in sorted(data["nodes"], key=lambda x: int(x.get("priority", 999)))
        ]
    else:
        data["execution_order"] = [qid for qid in data["execution_order"] if qid in node_ids]
        if not data["execution_order"]:
            data["execution_order"] = [data["nodes"][0]["id"]]

    if not isinstance(data["coverage_map"], dict):
        data["coverage_map"] = {}

    for output in req.required_outputs:
        ids = data["coverage_map"].get(output)
        if isinstance(ids, str):
            ids = [ids]
        if not ids:
            data["coverage_map"][output] = [data["nodes"][0]["id"]]
        else:
            valid_ids = [qid for qid in ids if qid in node_ids]
            data["coverage_map"][output] = valid_ids or [data["nodes"][0]["id"]]

    return data


def validate_and_repair(data: dict[str, Any], req: SectionPlannerRequest) -> dict[str, Any]:
    flags = data.setdefault("data_quality_flags", [])

    missing_outputs = [
        output
        for output in req.required_outputs
        if output not in data.get("coverage_map", {}) or not data["coverage_map"][output]
    ]
    if missing_outputs:
        flags.append(f"coverage_map_missing_outputs: {missing_outputs}")
        for output in missing_outputs:
            data["coverage_map"][output] = [data["nodes"][0]["id"]]

    level_1_nodes = [n for n in data["nodes"] if int(n.get("level", 0)) == 1]
    if len(level_1_nodes) < 3:
        flags.append("planner_generated_fewer_than_3_sub_questions")
    if len(level_1_nodes) > 7:
        flags.append("planner_generated_more_than_7_sub_questions")

    empty_questions = [n["id"] for n in data["nodes"] if not n.get("question")]
    if empty_questions:
        flags.append(f"empty_question_nodes: {empty_questions}")

    return data


def to_plan(data: dict[str, Any]) -> SectionResearchPlan:
    nodes = [
        ResearchQuestionNode.model_validate(n)
        for n in data["nodes"]
    ]
    return SectionResearchPlan(
        ticker=data["ticker"],
        section_id=data["section_id"],
        section_title=data["section_title"],
        planning_thesis=data.get("planning_thesis", ""),
        root_question=data.get("root_question", ""),
        nodes=nodes,
        coverage_map=data.get("coverage_map", {}),
        execution_order=data.get("execution_order", []),
        data_quality_flags=data.get("data_quality_flags", []),
        planner_notes=data.get("planner_notes"),
    )


def finalize_plan_from_llm_output(
    llm_output: dict[str, Any],
    req: SectionPlannerRequest,
) -> SectionResearchPlan:
    data = normalize_plan_dict(dict(llm_output), req)
    data = validate_and_repair(data, req)
    return to_plan(data)
