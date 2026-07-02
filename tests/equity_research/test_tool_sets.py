"""Tests for section research tool sets and router."""

from tradingagents.equity_research.tools.tool_sets import (
    EXECUTOR_TOOL_SETS,
    infer_tool_group,
    route_tool_group_from_state,
)


def test_step_action_maps_to_group():
    assert infer_tool_group(step_action="search") == "retrieval"
    assert infer_tool_group(step_action="calculate") == "computation"
    assert infer_tool_group(step_action="synthesize") == "action"


def test_tool_call_name_overrides_action():
    assert infer_tool_group(
        step_action="search",
        tool_names=["calculator"],
    ) == "computation"


def test_route_from_active_step():
    state = {
        "active_step": {
            "action": "fetch_primary",
            "description": "Fetch 10-K filing",
            "tool_hints": ["filings_search"],
        },
        "messages": [],
    }
    assert route_tool_group_from_state(state) == "retrieval"


def test_executor_tool_sets_partition_catalog():
    all_tools = set()
    for names in EXECUTOR_TOOL_SETS.values():
        overlap = all_tools.intersection(names)
        assert not overlap, f"duplicate tools across groups: {overlap}"
        all_tools.update(names)
