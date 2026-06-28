"""Parameterized query planner node for research subgraphs."""

from __future__ import annotations

from collections.abc import Callable
from difflib import SequenceMatcher
from typing import Any

from tradingagents.equity_research.agents.consensus.structured_invoke import invoke_structured_with_retry
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.consensus_schemas import QueryItem, QueryPlan


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def create_query_planner_node(
    deps: EquityResearchDeps,
    *,
    prompt_builder: Callable[[dict[str, Any]], str],
    max_queries: int,
    use_default_if_empty: bool,
    normalize_fn: Callable[[list[QueryItem], str, bool], list[QueryItem]],
    agent_name: str,
    trace_name: str | None = None,
    executed_queries_fn: Callable[[dict[str, Any]], list[str]] | None = None,
    fallback_plan: Callable[[dict[str, Any]], QueryPlan] | None = None,
    extend_queue: bool = False,
):
    agent_trace = trace_name or agent_name

    def query_planner(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            prompt = prompt_builder(state)

            def _fallback() -> QueryPlan:
                if fallback_plan:
                    return fallback_plan(state)
                return QueryPlan(queries=[])

            plan = invoke_structured_with_retry(
                deps.deep_llm,
                QueryPlan,
                prompt,
                agent_name=agent_name,
                max_attempts=_max_retries(deps),
                fallback=_fallback,
            )
            new_items = normalize_fn(plan.queries, ticker, use_default_if_empty)[:max_queries]

            if executed_queries_fn:
                executed = executed_queries_fn(state)
            else:
                executed = state.get("executed_queries", [])

            filtered: list[QueryItem] = []
            for item in new_items:
                if any(_similarity(item.query, prev) > 0.7 for prev in executed):
                    continue
                filtered.append(item)

            if extend_queue:
                queue = list(state.get("query_queue", []))
                queue.extend(q.model_dump() for q in filtered)
            else:
                queue = [q.model_dump() for q in filtered]

            updates: dict[str, Any] = {"query_queue": queue}
            updates.update(deps.trace({**state, **updates}, agent_trace, {
                "new_queries": len(filtered),
            }))
            return updates
        except Exception as exc:
            errors.append(f"{agent_name}: {exc}")
            return {"errors": errors}

    return query_planner
