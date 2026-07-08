"""Tests for structured enforcement in section merge."""

from tradingagents.equity_research.tasks.section_research.merge import (
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

