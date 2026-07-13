"""Semantic tool groups for section research executor."""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.tools import BaseTool

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.tools.lc import STATIC_LANGCHAIN_TOOLS
from tradingagents.equity_research.tools.lc.memory import make_memory_search_tools
from tradingagents.equity_research.tools.lc.finance import make_filings_search_tool
from tradingagents.equity_research.tools.lc.search import make_web_search_tool

ToolGroupId = Literal["retrieval", "computation", "action"]

TOOL_GROUP_IDS: tuple[ToolGroupId, ...] = ("retrieval", "computation", "action")

# Tools allowed per executor group (subset of section-research executor catalog).
EXECUTOR_TOOL_SETS: dict[ToolGroupId, tuple[str, ...]] = {
    "retrieval": (
        # Primary data
        "filings_search",
        "filing_reader",
        "financial_statement_fetch",
        "transcript_search",
        # Web
        "web_search",
        "news_search",
        # Memory read
        "memory_retrieve",
        "search_evidence",
        "search_claims",
        "search_assumptions",
        "search_consensus",
        # "search_conflicts",
        # "search_memory_timeline",
        # "search_research_context",
        # Document
        # "table_extractor",
        # "document_chunker",
        # "reference_parser",
        # Todos
        "list_research_todos",
        "get_next_research_todo",
        "update_research_todo_status",
        # Findings cache
        "findings_cache_read",
        "findings_cache_write",
    ),
    "computation": (
        "calculator",
        "time_series_analyzer",
        "conflict_detector",
        "citation_checker",
        "claim_evidence_checker",
        # Read-only memory fallback when step payload is thin
        "search_evidence",
        "search_claims",
        "findings_cache_read",
    ),
    "action": (
        # Todo management
        "list_research_todos",
        "add_research_todo",
        "remove_research_todo",
        "update_research_todo_status",
        "get_next_research_todo",
        # Memory write
        "memory_write",
        "store_evidence",
        # Findings cache
        "findings_cache_write",
        "findings_cache_read",
    ),
}

_TOOL_TO_GROUP: dict[str, ToolGroupId] = {}
for group_id, names in EXECUTOR_TOOL_SETS.items():
    for name in names:
        _TOOL_TO_GROUP[name] = group_id

# Deterministic action → group mapping (replaces _STEP_ACTION_DEFAULT_GROUP)
ACTION_TO_GROUP: dict[str, ToolGroupId] = {
    "fetch_primary": "retrieval",
    "search": "retrieval",
    "extract": "retrieval",
    "calculate": "computation",
    "compare": "computation",
    "verify": "computation",
    "synthesize": "action",
}

_RETRIEVAL_KEYWORDS = (
    "search", "fetch", "filing", "transcript", "news", "web", "document",
    "extract", "primary", "source", "evidence", "retrieve",
)
_COMPUTATION_KEYWORDS = (
    "calculat", "compute", "metric", "formula", "model", "sensitivity",
    "regression", "statistic", "time series", "compare", "verify", "ratio",
)
_ACTION_KEYWORDS = (
    "todo", "write", "store", "memory", "update status", "add task",
    "synthesize", "answer card", "queue",
)


def tool_group_node_name(group_id: ToolGroupId, *, prefix: str = "executor_tools") -> str:
    return f"{prefix}_{group_id}"


def group_for_tool_name(tool_name: str) -> ToolGroupId | None:
    return _TOOL_TO_GROUP.get(tool_name)


def infer_tool_group(
    *,
    step_action: str | None = None,
    tool_hints: list[str] | None = None,
    description: str = "",
    tool_names: list[str] | None = None,
) -> ToolGroupId:
    """Infer tool group with priority: tool_names > step_action > tool_hints > keywords."""
    
    # 1. Tool names from last AIMessage tool_calls → direct group lookup
    if tool_names:
        for name in tool_names:
            group = group_for_tool_name(name)
            if group:
                return group

    # 2. Step action → ACTION_TO_GROUP dict lookup
    action = (step_action or "").strip().lower()
    if action in ACTION_TO_GROUP:
        return ACTION_TO_GROUP[action]

    # 3. Tool hints from active step → majority vote
    if tool_hints:
        groups = {group_for_tool_name(h) for h in tool_hints if group_for_tool_name(h)}
        groups.discard(None)  # type: ignore[arg-type]
        if len(groups) == 1:
            return next(iter(groups))  # type: ignore[arg-type]

    # 4. Description keyword matching (last resort, with fixed priority: action > computation > retrieval)
    text = f"{description} {' '.join(tool_hints or [])}".lower()
    if any(k in text for k in _ACTION_KEYWORDS):
        return "action"
    if any(k in text for k in _COMPUTATION_KEYWORDS):
        return "computation"
    if any(k in text for k in _RETRIEVAL_KEYWORDS):
        return "retrieval"
    
    # Default to retrieval
    return "retrieval"


def route_tool_group_from_state(state: dict[str, Any]) -> ToolGroupId:
    active_step = state.get("active_step") or {}
    messages = state.get("messages") or []
    tool_names: list[str] = []
    if messages:
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        for call in tool_calls:
            name = call.get("name") if isinstance(call, dict) else getattr(call, "name", None)
            if name:
                tool_names.append(str(name))

    return infer_tool_group(
        step_action=str(active_step.get("action", "")),
        tool_hints=list(active_step.get("tool_hints") or []),
        description=str(active_step.get("description", "")),
        tool_names=tool_names,
    )


def resolve_executor_tool_names(
    task_profile: TaskProfile,
    group_id: ToolGroupId,
) -> list[str]:
    """Resolve tool names for a group, filtered by allowlist if present."""
    allowed = set(task_profile.extra_config.get("executor_langchain_tool_names", []))
    group_names = list(EXECUTOR_TOOL_SETS[group_id])
    if allowed:
        group_names = [n for n in group_names if n in allowed]
    return group_names


def build_tools_for_group(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    group_id: ToolGroupId,
) -> list[BaseTool]:
    """Build tools for a specific group, with dynamic deps-aware construction."""
    tools: list[BaseTool] = []
    names = resolve_executor_tool_names(task_profile, group_id)
    
    if group_id in ("retrieval", "computation"):
        # Dynamic deps-aware tools (memory search; retrieval also gets web/filings)
        dynamic = {t.name: t for t in make_memory_search_tools(deps)}
        if group_id == "retrieval":
            dynamic["web_search"] = make_web_search_tool(deps)
            dynamic["filings_search"] = make_filings_search_tool(deps)

        for name in names:
            if name in dynamic:
                tools.append(dynamic[name])
            elif name in STATIC_LANGCHAIN_TOOLS:
                tools.append(STATIC_LANGCHAIN_TOOLS[name])
        return tools

    # Action group: static tools only
    for name in names:
        if name in STATIC_LANGCHAIN_TOOLS:
            tools.append(STATIC_LANGCHAIN_TOOLS[name])
    return tools


def build_executor_tool_set_nodes(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    prefix: str = "executor_tools",
) -> dict[str, Any]:
    from langgraph.prebuilt import ToolNode

    nodes: dict[str, Any] = {}
    for group_id in TOOL_GROUP_IDS:
        node_name = tool_group_node_name(group_id, prefix=prefix)
        base_node = ToolNode(build_tools_for_group(deps, task_profile, group_id))

        def _make_wrapped(node, group):
            def wrapped(state: dict[str, Any]) -> dict[str, Any]:
                return node.invoke(state)

            return wrapped

        nodes[node_name] = _make_wrapped(base_node, group_id)
    return nodes
