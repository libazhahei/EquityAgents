"""Batch search executor node for research subgraphs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.search_memory import (
    append_search_record,
    queries_from_memory,
    record_from_evidence,
)
from tradingagents.equity_research.tools.perplexity_tool import execute_perplexity_search


def _append_documents(documents: list[dict], doc_ids: list[str]) -> list[dict]:
    new_docs = list(documents)
    existing_doc_ids = {d.get("doc_id") for d in new_docs}
    for doc_id in doc_ids:
        if doc_id not in existing_doc_ids:
            new_docs.append({"doc_id": doc_id})
            existing_doc_ids.add(doc_id)
    return new_docs


def _batch_concurrency(deps: EquityResearchDeps, batch_size: int) -> int:
    er = deps.config.get("equity_research", {}) or {}
    configured = er.get("batch_search_concurrency", batch_size)
    try:
        return max(1, min(int(configured), batch_size))
    except (TypeError, ValueError):
        return max(1, batch_size)


def create_executor_node(
    deps: EquityResearchDeps,
    task_profile: TaskProfile,
    *,
    batch_size: int = 5,
    trace_name: str | None = None,
    search_fn: Callable[..., Any] | None = None,
):
    run_search = search_fn or execute_perplexity_search
    agent_trace = trace_name or f"{task_profile.task_id}_query_executor"

    def _run_one_query(
        item: dict[str, Any],
        *,
        ticker: str,
        iteration: int,
    ) -> tuple[dict[str, Any] | None, Any, list[str], int, str | None]:
        query = item.get("query", "")
        target_dimension = item.get("target_dimension", "narrative_framework")
        mode = item.get("mode", "exploratory")
        try:
            evidence = run_search(
                deps,
                query=query,
                mode=mode,
                target_dimension=target_dimension,
                ticker=ticker,
            )
            evidence_dict = evidence.model_dump()
            record = record_from_evidence(
                deps, evidence, iteration=iteration, mode=str(mode), query=query
            )
            return evidence_dict, record, evidence.doc_ids, 1, None
        except Exception as exc:
            return None, None, [], 0, f"query failed ({query[:60]}): {exc}"

    def query_batch_executor(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        queue = list(state.get("query_queue", []))
        if not queue:
            return {}

        queue.sort(key=lambda q: int(q.get("priority", 0)), reverse=True)
        to_run = queue[:batch_size]
        remaining = queue[batch_size:]

        search_memory = list(state.get("search_memory", []))
        buffer = list(state.get("evidence_buffer", []))
        pending = list(state.get("pending_evidence", []))
        new_docs = list(state.get("documents", []))
        api_calls = int(state.get("api_calls", 0))
        iteration = int(state.get("iterations", state.get("consensus_iterations", 0)))
        dimensions_run: list[str] = []
        concurrency = _batch_concurrency(deps, len(to_run))

        try:
            results_by_priority: dict[int, tuple] = {}
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(
                        _run_one_query,
                        item,
                        ticker=ticker,
                        iteration=iteration,
                    ): item
                    for item in to_run
                }
                for fut in as_completed(futures):
                    item = futures[fut]
                    priority = int(item.get("priority", 0))
                    dimensions_run.append(item.get("target_dimension", "narrative_framework"))
                    evidence_dict, record, doc_ids, calls, err = fut.result()
                    if err:
                        errors.append(err)
                        continue
                    if evidence_dict is None or record is None:
                        continue
                    results_by_priority[priority] = (evidence_dict, record, doc_ids, calls)

            for priority in sorted(results_by_priority.keys(), reverse=True):
                evidence_dict, record, doc_ids, calls = results_by_priority[priority]
                buffer.append(evidence_dict)
                pending.append(evidence_dict)
                search_memory = append_search_record(search_memory, record)
                new_docs = _append_documents(new_docs, doc_ids)
                api_calls += calls

            executed = queries_from_memory(search_memory)
            updates: dict[str, Any] = {
                "query_queue": remaining,
                "executed_queries": executed,
                "search_memory": search_memory,
                "evidence_buffer": buffer,
                "pending_evidence": pending,
                "documents": new_docs,
                "api_calls": api_calls,
            }
            if errors:
                updates["errors"] = errors
            updates.update(deps.trace({**state, **updates}, agent_trace, {
                "batch_size": len(to_run),
                "dimensions": dimensions_run,
                "concurrency": concurrency,
            }))
            return updates
        except Exception as exc:
            errors.append(f"query_batch_executor: {exc}")
            return {
                "errors": errors,
                "query_queue": remaining,
                "evidence_buffer": buffer,
                "pending_evidence": pending,
                "search_memory": search_memory,
                "documents": new_docs,
                "api_calls": api_calls,
            }

    return query_batch_executor
