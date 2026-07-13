"""Tests for structured enforcement in section merge."""

from tradingagents.equity_research.tasks.section_research.merge import (
    apply_evidence_heuristic,
    enforce_structured_answer_requirements,
)
from tradingagents.equity_research.tasks.section_research.schemas import (
    AnswerCard,
    SectionResearchView,
)


def test_enforce_structured_requirements_adds_gaps():
    view = SectionResearchView(
        ticker="NVDA",
        section_id="3_business_model",
        answer_cards={
            "q1": AnswerCard(question_id="q1", question="What drives GM?"),
        },
    )
    gaps = enforce_structured_answer_requirements(view)
    assert "q1:missing_structured_quant" in gaps
    assert "q1:missing_structured_source" in gaps
    assert view.answer_cards["q1"].data_availability_notes


def test_apply_evidence_heuristic_dedupes_by_evidence_id():
    view = SectionResearchView(
        ticker="NVDA",
        section_id="3_business_model",
        answer_cards={},
    )
    pending = [{
        "question_id": "q1",
        "evidence_id": "ev_1",
        "snippet": "Gross margin expanded on mix.",
        "source": "10-K",
    }]
    apply_evidence_heuristic(view, pending)
    apply_evidence_heuristic(view, pending)
    card = view.answer_cards["q1"]
    assert len(card.verified_facts) == 1
    assert card.evidence_ids == ["ev_1"]
    assert card.confidence == 0.1


def test_apply_evidence_heuristic_dedupes_by_snippet_prefix_without_id():
    view = SectionResearchView(
        ticker="NVDA",
        section_id="3_business_model",
        answer_cards={},
    )
    pending = [{
        "question_id": "q1",
        "snippet": "Operating leverage improved in FY26.",
        "source": "earnings",
    }]
    apply_evidence_heuristic(view, pending)
    apply_evidence_heuristic(view, pending)
    card = view.answer_cards["q1"]
    assert len(card.verified_facts) == 1
    assert card.evidence_ids == []

