"""Tests for section research tool sets and router."""

from unittest.mock import Mock

from tradingagents.equity_research.tools.tool_sets import (
    ACTION_TO_GROUP,
    EXECUTOR_TOOL_SETS,
    infer_tool_group,
    resolve_executor_tool_names,
    route_tool_group_from_state,
)


def test_step_action_maps_to_group():
    """Test all 5 action → group mappings."""
    assert infer_tool_group(step_action="orient") == "retrieval"
    assert infer_tool_group(step_action="fetch_primary") == "retrieval"
    assert infer_tool_group(step_action="search") == "retrieval"
    assert infer_tool_group(step_action="verify") == "computation"
    assert infer_tool_group(step_action="synthesize") == "action"


def test_tool_call_name_overrides_action():
    """Tool name from last AIMessage takes priority over step action."""
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
    """No tool should appear in more than one group."""
    all_tools = set()
    for names in EXECUTOR_TOOL_SETS.values():
        overlap = all_tools.intersection(names)
        assert not overlap, f"duplicate tools across groups: {overlap}"
        all_tools.update(names)


def test_no_batch_perplexity_in_section_executor():
    """batch_perplexity_search is NOT in any EXECUTOR_TOOL_SETS group (generic executor only)."""
    all_tools = set()
    for names in EXECUTOR_TOOL_SETS.values():
        all_tools.update(names)
    assert "batch_perplexity_search" not in all_tools


def test_no_batch_light_grounding_in_section_executor():
    """batch_light_grounding_search is NOT in any EXECUTOR_TOOL_SETS group (planner-only tool)."""
    all_tools = set()
    for names in EXECUTOR_TOOL_SETS.values():
        all_tools.update(names)
    assert "batch_light_grounding_search" not in all_tools


def test_resolve_executor_tool_names_with_allowlist():
    """Verify allowlist filtering works correctly."""
    # Create a mock task profile with an allowlist
    profile = Mock()
    profile.extra_config = {
        "executor_langchain_tool_names": ["calculator", "web_search"],
    }
    
    # Test retrieval group filtering
    names = resolve_executor_tool_names(profile, "retrieval")
    assert "web_search" in names
    assert "filings_search" not in names  # Not in allowlist
    
    # Test computation group filtering
    names = resolve_executor_tool_names(profile, "computation")
    assert "calculator" in names
    assert "citation_checker" not in names  # Not in allowlist


def test_keyword_routing_priority():
    """Verify action-based routing takes priority over keyword matching."""
    # Step action should take priority even if description has computation keywords
    assert infer_tool_group(
        step_action="search",
        description="Calculate the revenue growth rate",
    ) == "retrieval"
    
    # Step action should take priority even if description has action keywords
    assert infer_tool_group(
        step_action="fetch_primary",
        description="Store the filing data",
    ) == "retrieval"


def test_action_to_group_dict():
    """Verify ACTION_TO_GROUP dict has all expected mappings."""
    expected = {
        "orient": "retrieval",
        "fetch_primary": "retrieval",
        "search": "retrieval",
        "calculate": "computation",
        "compare": "computation",
        "verify": "computation",
        "synthesize": "action",
    }
    for action, group in expected.items():
        assert ACTION_TO_GROUP[action] == group
