"""Tests for SectionResearchSubgraph topology."""

from unittest.mock import MagicMock

from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.tasks.section_research.profile import (
    EXECUTOR_LANGCHAIN_TOOL_NAMES,
    SECTION_RESEARCH_TASK_PROFILE,
)


def test_section_subgraph_nodes():
    deps = MagicMock()
    graph = SectionResearchSubgraph(deps, SECTION_RESEARCH_TASK_PROFILE).build()
    nodes = set(graph.nodes.keys())
    assert "initial_planner" in nodes
    assert "executor" in nodes
    assert "executor_tool_router" in nodes
    assert "executor_apply" in nodes
    assert "reflector" in nodes
    assert "loop_planner" in nodes
    assert "executor_tools_retrieval" in nodes
    assert "executor_tools_computation" in nodes
    assert "executor_tools_action" in nodes


def test_executor_tool_names_in_profile():
    assert "list_research_todos" in EXECUTOR_LANGCHAIN_TOOL_NAMES
    assert "filings_search" in EXECUTOR_LANGCHAIN_TOOL_NAMES
