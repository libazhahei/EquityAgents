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
    """Test action → group mappings."""
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
    """No unexpected tool should appear in more than one group."""
    allowed_overlap = {
        "list_research_todos",
        "get_next_research_todo",
        "update_research_todo_status",
        "findings_cache_write",
        "findings_cache_read",
        "search_evidence",
        "search_claims",
    }
    all_tools: dict[str, str] = {}
    for group, names in EXECUTOR_TOOL_SETS.items():
        for name in names:
            if name in all_tools and name not in allowed_overlap:
                raise AssertionError(f"duplicate tool {name} in {all_tools[name]} and {group}")
            all_tools[name] = group


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
        "fetch_primary": "retrieval",
        "search": "retrieval",
        "extract": "retrieval",
        "calculate": "computation",
        "compare": "computation",
        "verify": "computation",
        "synthesize": "action",
    }
    for action, group in expected.items():
        assert ACTION_TO_GROUP[action] == group
    assert "orient" not in ACTION_TO_GROUP


def test_computation_group_includes_readonly_memory():
    assert "search_evidence" in EXECUTOR_TOOL_SETS["computation"]
    assert "search_claims" in EXECUTOR_TOOL_SETS["computation"]
    assert "findings_cache_read" in EXECUTOR_TOOL_SETS["computation"]
