"""Tests for assumption view merge and deduplication."""

from tradingagents.equity_research.tasks.assumption.merge import merge_assumption_view
from tradingagents.equity_research.tasks.assumption.schemas import (
    AssumptionItem,
    AssumptionView,
    AssumptionViewUpdate,
    ResearchSuggestion,
)


def test_merge_assumption_map_by_id():
    view = AssumptionView(
        ticker="NVDA",
        assumption_map=[
            AssumptionItem(id="A1", statement="The market is implicitly assuming that demand stays strong"),
        ],
    )
    update = AssumptionViewUpdate(
        assumption_map=[
            AssumptionItem(
                id="A1",
                statement="The market is implicitly assuming that demand stays strong",
                falsification_tests=["Hyperscaler capex slows"],
            ),
        ],
    )
    merged = merge_assumption_view(view, update)
    assert len(merged.assumption_map) == 1
    assert merged.assumption_map[0].falsification_tests == ["Hyperscaler capex slows"]


def test_merge_research_suggestions_dedupes_similar_direction():
    view = AssumptionView(
        research_suggestions=[
            ResearchSuggestion(direction="Track Blackwell ramp and margin bridge", priority=2),
        ],
    )
    update = AssumptionViewUpdate(
        research_suggestions=[
            ResearchSuggestion(
                direction="Track Blackwell ramp and gross margin bridge",
                priority=1,
                rationale="Need margin disclosure",
            ),
        ],
    )
    merged = merge_assumption_view(view, update)
    assert len(merged.research_suggestions) == 1
    assert merged.research_suggestions[0].priority == 1
