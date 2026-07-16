"""Trajectory quality checks from LangSmith child runs or local research_traces."""

from __future__ import annotations

from collections import Counter
from typing import Any

from evaluation.section_research.types import ChildRunSummary, EvalBundle
from tradingagents.equity_research.tasks.section_research.profile import (
    EXECUTOR_LANGCHAIN_TOOL_NAMES,
)

ALLOWED_TOOLS = set(EXECUTOR_LANGCHAIN_TOOL_NAMES)
# Soft-allow LangGraph / LLM run names that are not tools
NON_TOOL_RUN_TYPES = {"chain", "llm", "prompt", "parser", "retriever"}

DEFAULT_TOOL_BUDGET = 100
REPEATED_QUERY_SOFT_LIMIT = 3


def _tool_calls_from_bundle(bundle: EvalBundle) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    for child in bundle.child_runs:
        if isinstance(child, ChildRunSummary):
            if child.run_type == "tool" or child.name in ALLOWED_TOOLS:
                calls.append({
                    "name": child.name,
                    "run_type": child.run_type,
                    "inputs": child.inputs,
                })
        elif isinstance(child, dict):
            name = child.get("name") or ""
            run_type = child.get("run_type") or ""
            if run_type == "tool" or name in ALLOWED_TOOLS:
                calls.append({
                    "name": name,
                    "run_type": run_type,
                    "inputs": child.get("inputs") or {},
                })

    if calls:
        return calls

    # Fallback: local research_traces / api-ish signals
    traces = bundle.final_state.get("research_traces") or []
    if isinstance(traces, list):
        for tr in traces:
            if not isinstance(tr, dict):
                continue
            tool = tr.get("tool") or tr.get("name") or tr.get("node")
            if tool:
                calls.append({
                    "name": str(tool),
                    "run_type": tr.get("run_type") or "trace",
                    "inputs": tr.get("inputs") or tr.get("args") or {},
                })
    return calls


def _query_key(inputs: dict[str, Any]) -> str | None:
    for key in ("query", "q", "search_query", "question"):
        if key in inputs and inputs[key]:
            return f"{key}={str(inputs[key]).strip().lower()}"
    return None


def score_trajectory(
    bundle: EvalBundle,
    *,
    tool_budget: int = DEFAULT_TOOL_BUDGET,
) -> tuple[float, dict[str, Any]]:
    calls = _tool_calls_from_bundle(bundle)
    unknown: list[str] = []
    allowed_hits = 0
    query_counter: Counter[str] = Counter()

    for call in calls:
        name = call.get("name") or ""
        run_type = call.get("run_type") or ""
        if run_type in NON_TOOL_RUN_TYPES and name not in ALLOWED_TOOLS:
            continue
        if name in ALLOWED_TOOLS or run_type == "trace":
            # research_traces node names may not be tools — soft-pass traces
            if name in ALLOWED_TOOLS or run_type == "trace":
                if name in ALLOWED_TOOLS:
                    allowed_hits += 1
                q = _query_key(call.get("inputs") or {})
                if q:
                    query_counter[q] += 1
            continue
        if run_type == "tool" or name:
            if name and name not in ALLOWED_TOOLS:
                unknown.append(name)

    tool_call_count = sum(1 for c in calls if c.get("run_type") == "tool" or c.get("name") in ALLOWED_TOOLS)
    repeated = {k: v for k, v in query_counter.items() if v > REPEATED_QUERY_SOFT_LIMIT}
    over_budget = tool_call_count >= tool_budget

    # Scoring
    score = 1.0
    if unknown:
        score -= min(0.5, 0.1 * len(set(unknown)))
    if over_budget:
        score -= 0.3
    if repeated:
        score -= min(0.3, 0.05 * len(repeated))
    if tool_call_count == 0 and not bundle.final_state.get("research_traces"):
        # No trajectory signal — neutral-low rather than perfect
        score = min(score, 0.5)

    details = {
        "tool_call_count": tool_call_count,
        "allowed_hits": allowed_hits,
        "unknown_tools": sorted(set(unknown)),
        "repeated_queries": repeated,
        "over_budget": over_budget,
        "budget": tool_budget,
        "has_child_runs": bool(bundle.child_runs),
    }
    return round(max(0.0, min(1.0, score)), 4), details


def evaluate_trajectory(bundle: EvalBundle, *, tool_budget: int = DEFAULT_TOOL_BUDGET) -> dict[str, Any]:
    score, details = score_trajectory(bundle, tool_budget=tool_budget)
    return {"trajectory_score": score, "details": details}
