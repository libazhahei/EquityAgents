"""Tool group router — classify executor tool space before ToolNode."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.tools.tool_sets import (
    TOOL_GROUP_IDS,
    ToolGroupId,
    route_tool_group_from_state,
    tool_group_node_name,
)


def create_executor_tool_router_node(*, prefix: str = "executor_tools"):
    def router(state: dict[str, Any]) -> dict[str, Any]:
        group_id = route_tool_group_from_state(state)
        return {
            "_executor_tool_group": group_id,
            "_executor_tool_node": tool_group_node_name(group_id, prefix=prefix),
        }

    return router


def executor_tool_group_router(state: dict[str, Any], *, prefix: str = "executor_tools") -> str:
    group_id = state.get("_executor_tool_group")
    if group_id in TOOL_GROUP_IDS:
        return tool_group_node_name(group_id, prefix=prefix)  # type: ignore[arg-type]
    resolved: ToolGroupId = route_tool_group_from_state(state)
    return tool_group_node_name(resolved, prefix=prefix)
