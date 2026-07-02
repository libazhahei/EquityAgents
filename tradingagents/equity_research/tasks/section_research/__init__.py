"""Section research task — autonomous per-section deep research loop."""

from tradingagents.equity_research.tasks.section_research.schemas import (
    AnswerCard,
    ResearchBrief,
    ResearchTodoList,
    SectionResearchOutput,
    SectionResearchPlan,
    SectionResearchView,
)

__all__ = [
    "SECTION_RESEARCH_TASK_PROFILE",
    "AnswerCard",
    "ResearchBrief",
    "ResearchTodoList",
    "SectionResearchOutput",
    "SectionResearchPlan",
    "SectionResearchView",
]


def __getattr__(name: str):
    if name == "SECTION_RESEARCH_TASK_PROFILE":
        from tradingagents.equity_research.tasks.section_research.profile import (
            SECTION_RESEARCH_TASK_PROFILE,
        )
        return SECTION_RESEARCH_TASK_PROFILE
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
