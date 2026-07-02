"""Generic research subgraph runtime framework."""

from tradingagents.equity_research.runtime.exploration_graph import (
    ExplorationGraph,
    ExplorationNode,
)
from tradingagents.equity_research.runtime.state import AgentState, empty_agent_state
from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile

__all__ = [
    "AgentState",
    "ExplorationGraph",
    "ExplorationNode",
    "GenericResearchSubgraph",
    "SectionResearchSubgraph",
    "TaskProfile",
    "empty_agent_state",
]


def __getattr__(name: str):
    if name == "SectionResearchSubgraph":
        from tradingagents.equity_research.runtime.section_research_subgraph import (
            SectionResearchSubgraph,
        )
        return SectionResearchSubgraph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
