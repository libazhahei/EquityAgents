"""End-to-end deterministic checks for section research outputs."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from evaluation.section_research.types import EvalBundle
from tradingagents.equity_research.tasks.section_research.schemas import (
    SectionCoverageEvaluation,
    SectionCoverageReport,
    SectionResearchOutput,
    SectionResearchPlan,
)


def _section_output(state: dict[str, Any], section_id: str) -> dict[str, Any]:
    out = state.get("section_research_output")
    if isinstance(out, dict) and out:
        return out
    outputs = state.get("section_research_outputs") or {}
    if isinstance(outputs, dict):
        candidate = outputs.get(section_id) or {}
        if isinstance(candidate, dict):
            return candidate
    return {}


def score_completion(bundle: EvalBundle) -> tuple[float, dict[str, Any]]:
    state = bundle.final_state
    section_out = _section_output(state, bundle.section_id)
    text = (
        (section_out.get("final_section_text") or "")
        or (state.get("final_report") or "")
        or (section_out.get("executive_summary") or "")
    )
    text = text.strip() if isinstance(text, str) else ""
    has_text = len(text) >= 80

    answer_cards = section_out.get("answer_cards") or state.get("answer_cards") or {}
    plan = section_out.get("research_plan") or state.get("research_plan") or {}
    tasks = plan.get("tasks") if isinstance(plan, dict) else []
    expected_questions = 0
    if isinstance(tasks, list) and tasks:
        expected_questions = len(tasks)
    elif isinstance(plan, dict) and plan.get("execution_order"):
        expected_questions = len(plan["execution_order"])

    card_count = len(answer_cards) if isinstance(answer_cards, dict) else 0
    cards_ok = True
    if expected_questions > 0:
        cards_ok = card_count > 0

    checks = {
        "has_substantial_text": has_text,
        "text_length": len(text),
        "answer_card_count": card_count,
        "expected_questions": expected_questions,
        "cards_ok": cards_ok,
    }
    score = 0.0
    if has_text:
        score += 0.7
    if cards_ok:
        score += 0.3
    elif expected_questions == 0 and has_text:
        score = 1.0
    return round(min(score, 1.0), 4), checks


def score_schema(bundle: EvalBundle) -> tuple[float, dict[str, Any]]:
    state = bundle.final_state
    section_out = _section_output(state, bundle.section_id)
    details: dict[str, Any] = {"ok": [], "errors": []}
    checks = 0
    passed = 0

    def _try(name: str, model_cls: type, payload: Any) -> None:
        nonlocal checks, passed
        if payload is None or payload == {} or payload == []:
            return
        checks += 1
        try:
            if hasattr(payload, "model_dump"):
                payload = payload.model_dump()
            model_cls.model_validate(payload)
            passed += 1
            details["ok"].append(name)
        except ValidationError as exc:
            details["errors"].append({"name": name, "error": str(exc)[:400]})

    if section_out:
        _try("SectionResearchOutput", SectionResearchOutput, section_out)
    plan = section_out.get("research_plan") or state.get("research_plan")
    if plan:
        _try("SectionResearchPlan", SectionResearchPlan, plan)
    coverage = state.get("coverage_report")
    if coverage:
        # Prefer report shape; fall back to evaluation shape
        try:
            SectionCoverageReport.model_validate(coverage)
            checks += 1
            passed += 1
            details["ok"].append("SectionCoverageReport")
        except ValidationError:
            _try("SectionCoverageEvaluation", SectionCoverageEvaluation, coverage)

    if checks == 0:
        # Nothing structured to validate — incomplete run
        return 0.0, {**details, "checks": 0, "note": "no structured payloads"}

    score = passed / checks
    return round(score, 4), {**details, "checks": checks, "passed": passed}


def evaluate_end_to_end(bundle: EvalBundle) -> dict[str, Any]:
    completion, completion_details = score_completion(bundle)
    schema, schema_details = score_schema(bundle)
    return {
        "completion_score": completion,
        "schema_score": schema,
        "details": {
            "completion": completion_details,
            "schema": schema_details,
        },
    }
