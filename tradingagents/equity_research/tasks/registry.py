"""Task registry bootstrap."""

from __future__ import annotations

from tradingagents.equity_research.runtime.task_registry import TaskRegistry
from tradingagents.equity_research.tasks.assumption.profile import ASSUMPTION_TASK_PROFILE
from tradingagents.equity_research.tasks.consensus.profile import CONSENSUS_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.profile import SECTION_RESEARCH_TASK_PROFILE

_REGISTRY: TaskRegistry | None = None


def get_task_registry() -> TaskRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = TaskRegistry()
        _REGISTRY.register(CONSENSUS_TASK_PROFILE)
        _REGISTRY.register(ASSUMPTION_TASK_PROFILE)
        _REGISTRY.register(SECTION_RESEARCH_TASK_PROFILE)
    return _REGISTRY
