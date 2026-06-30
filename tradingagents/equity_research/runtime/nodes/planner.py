"""Parameterized query planner node for research subgraphs."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.dedupe import similarity
from tradingagents.equity_research.runtime.utils.structured_invoke import invoke_structured_with_retry
from tradingagents.equity_research.state.consensus_schemas import QueryItem, QueryPlan


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def create_planner_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    mode: str = "initial",
):
    if mode == "initial":
        max_queries = task_profile.max_initial_queries
        use_default_if_empty = True
        extend_queue = False
        prompt_builder = task_profile.build_initial_planner_prompt
        agent_name = f"{task_profile.task_id}_planner"
        fallback_plan = None
        executed_queries_fn = None
    else:
        max_queries = task_profile.max_loop_queries
        use_default_if_empty = False
        extend_queue = True
        prompt_builder = task_profile.build_loop_planner_prompt
        agent_name = f"{task_profile.task_id}_query_planner"
        from tradingagents.equity_research.runtime.utils.search_memory import queries_from_memory

        def fallback_plan(_state: dict[str, Any]) -> QueryPlan:
            return QueryPlan(queries=[])

        def executed_queries_fn(state: dict[str, Any]) -> list[str]:
            return queries_from_memory(state.get("search_memory", [])) or state.get("executed_queries", [])

    agent_trace = agent_name

    def query_planner(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            prompt = prompt_builder(deps, state)

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
            new_items = task_profile.normalize_queries_fn(
                plan.queries, ticker, use_default_if_empty,
            )[:max_queries]

            if executed_queries_fn:
                executed = executed_queries_fn(state)
            else:
                executed = state.get("executed_queries", [])

            filtered: list[QueryItem] = []
            for item in new_items:
                if any(similarity(item.query, prev) > 0.7 for prev in executed):
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
