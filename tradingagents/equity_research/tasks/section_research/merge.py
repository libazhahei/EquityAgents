"""Merge evidence and updates into section research view."""

from __future__ import annotations

import json
import uuid
from typing import Any

from tradingagents.equity_research.tasks.section_research.schemas import (
    AnswerCard,
    DataAvailabilityNote,
    SectionResearchView,
    SectionResearchViewUpdate,
)


def merge_section_view(
    view: SectionResearchView,
    update: SectionResearchViewUpdate,
) -> SectionResearchView:
    dump = update.model_dump(exclude_unset=True)
    if update.answer_cards:
        merged = dict(view.answer_cards)
        for qid, card in update.answer_cards.items():
            if qid in merged:
                existing = merged[qid]
                merged[qid] = AnswerCard(
                    **{**existing.model_dump(), **card.model_dump(exclude_unset=True)},
                )
            else:
                merged[qid] = card
        view.answer_cards = merged
        dump.pop("answer_cards", None)
    for key, value in dump.items():
        if value and hasattr(view, key):
            setattr(view, key, value)
    return view


def collect_evidence_for_question(state: dict[str, Any], question_id: str) -> list[dict]:
    """Gather evidence for a question from pending, buffer, and ledger."""
    qid = str(question_id)
    seen: set[str] = set()
    collected: list[dict] = []

    def _add(ev: dict) -> None:
        if not isinstance(ev, dict):
            return
        ev_qid = str(ev.get("question_id") or ev.get("target_dimension") or "")
        if ev_qid and ev_qid not in (qid, "general"):
            return
        eid = str(ev.get("evidence_id") or ev.get("fragment_id") or "")
        key = eid or str(ev.get("snippet") or ev.get("content") or "")[:80]
        if key in seen:
            return
        seen.add(key)
        item = dict(ev)
        item["question_id"] = qid
        collected.append(item)

    for ev in state.get("pending_evidence") or []:
        _add(ev)
    for ev in state.get("evidence_buffer") or []:
        _add(ev)
    for entry in state.get("evidence_ledger") or []:
        if isinstance(entry, dict):
            _add(entry)
    for frag in state.get("evidence_fragments") or []:
        if isinstance(frag, dict):
            _add(frag)

    return collected


def enforce_structured_answer_requirements(view: SectionResearchView) -> list[str]:
    gaps: list[str] = []
    for qid, card in view.answer_cards.items():
        has_quant = bool(card.quantified_claims)
        has_sources = bool(card.source_attributions)
        has_unavailable = any(n.status == "unavailable" for n in card.data_availability_notes)

        if not has_quant and not has_unavailable:
            card.open_gaps.append("Missing structured quantitative evidence")
            gaps.append(f"{qid}:missing_structured_quant")
        if not has_sources:
            card.open_gaps.append("Missing structured source metadata")
            gaps.append(f"{qid}:missing_structured_source")

        # Keep open_gaps deduplicated and stable.
        card.open_gaps = list(dict.fromkeys(card.open_gaps))

        # If no availability note exists, add a default pending note for traceability.
        if not card.data_availability_notes:
            card.data_availability_notes.append(
                DataAvailabilityNote(
                    metric="core_conclusion",
                    status="available" if has_quant else "unavailable",
                    rationale=(
                        "No structured quantitative claim found."
                        if not has_quant
                        else "Structured quantitative claim captured."
                    ),
                )
            )
    view.unresolved_gaps = list(dict.fromkeys([*view.unresolved_gaps, *gaps]))
    return gaps


def apply_evidence_heuristic(view: SectionResearchView, pending: list[dict]) -> None:
    for ev in pending:
        qid = str(ev.get("question_id") or ev.get("target_dimension") or "general")
        card = view.answer_cards.get(qid)
        if not card:
            card = AnswerCard(question_id=qid, question=ev.get("query", qid))
            view.answer_cards[qid] = card
        snippet = str(ev.get("snippet") or ev.get("content") or "")[:500]
        if snippet:
            card.verified_facts.append({
                "text": snippet,
                "source": ev.get("source", ""),
                "evidence_id": ev.get("evidence_id", ""),
            })
            card.evidence_ids.append(str(ev.get("evidence_id", "")))
        card.confidence = min(0.9, card.confidence + 0.1)


def build_answer_card_from_evidence(
    question_id: str,
    question: str,
    evidence: list[dict],
) -> AnswerCard:
    facts = []
    citations = []
    eids = []
    for ev in evidence:
        eid = str(ev.get("evidence_id") or ev.get("fragment_id") or uuid.uuid4().hex[:8])
        eids.append(eid)
        facts.append({
            "text": str(ev.get("snippet") or ev.get("content", ""))[:400],
            "source": ev.get("source", ""),
            "evidence_id": eid,
        })
        citations.append({
            "evidence_id": eid,
            "source": ev.get("source", ""),
            "url": ev.get("url", ""),
        })
    return AnswerCard(
        question_id=question_id,
        question=question,
        short_answer=f"Collected {len(facts)} evidence item(s) for {question_id}.",
        verified_facts=facts,
        evidence_ids=eids,
        citations=citations,
        confidence=0.5 if facts else 0.0,
        data_quality="medium" if facts else "low",
    )


def format_section_view(view: SectionResearchView) -> str:
    return view.to_legacy_summary()


def evaluation_to_report(evaluation: Any) -> Any:
    from tradingagents.equity_research.tasks.section_research.schemas import SectionCoverageReport

    return SectionCoverageReport(
        overall_score=evaluation.overall_score,
        plan_completion=evaluation.plan_completion,
        question_scores=evaluation.question_scores,
        coverage_outputs_completed=evaluation.coverage_outputs_completed,
        critical_gaps=evaluation.critical_gaps,
        data_quality_issues=evaluation.data_quality_issues,
        contradictions=evaluation.contradictions,
        recommended_next_action=evaluation.recommended_next_action,
        routing_decision=(
            "exit" if evaluation.recommended_next_action == "exit" else "continue"
        ),
    )


def default_coverage_report(view: SectionResearchView) -> Any:
    from tradingagents.equity_research.tasks.section_research.schemas import (
        PlanCompletion,
        SectionCoverageReport,
    )

    cards = view.answer_cards
    q_scores = {qid: card.confidence for qid, card in cards.items()}
    overall = sum(q_scores.values()) / len(q_scores) if q_scores else 0.0
    return SectionCoverageReport(
        overall_score=overall,
        plan_completion=PlanCompletion(),
        question_scores=q_scores,
        coverage_outputs_completed=[],
        critical_gaps=[],
        recommended_next_action="run_existing_queue" if overall < 0.75 else "exit",
        routing_decision="continue" if overall < 0.75 else "exit",
    )


def compute_plan_completion(plan_dict: dict[str, Any]) -> dict[str, Any]:
    from tradingagents.equity_research.tasks.section_research.schemas import (
        PlanCompletion,
        SectionResearchPlan,
    )

    plan = SectionResearchPlan.model_validate(plan_dict)
    tasks_total = len(plan.tasks)
    tasks_done = sum(1 for t in plan.tasks if t.status == "done")
    steps_total = sum(len(t.steps) for t in plan.tasks)
    steps_done = sum(1 for t in plan.tasks for s in t.steps if s.status == "done")
    blocked = [
        f"{t.task_id}:{s.step_id}"
        for t in plan.tasks
        for s in t.steps
        if s.status == "failed"
    ]
    return PlanCompletion(
        tasks_total=tasks_total,
        tasks_done=tasks_done,
        steps_total=steps_total,
        steps_done=steps_done,
        blocked_steps=blocked,
    ).model_dump()
