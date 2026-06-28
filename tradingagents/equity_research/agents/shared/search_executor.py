"""Batch search executor node for research subgraphs."""

from __future__ import annotations

from typing import Any, Callable

from tradingagents.equity_research.agents.consensus.search_memory import (
    append_search_record,
    queries_from_memory,
    record_from_evidence,
)
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.tools.perplexity_tool import execute_perplexity_search


def _append_documents(documents: list[dict], doc_ids: list[str]) -> list[dict]:
    new_docs = list(documents)
    existing_doc_ids = {d.get("doc_id") for d in new_docs}
    for doc_id in doc_ids:
        if doc_id not in existing_doc_ids:
            new_docs.append({"doc_id": doc_id})
            existing_doc_ids.add(doc_id)
    return new_docs


def create_search_batch_executor(
    deps: EquityResearchDeps,
    *,
    batch_size: int = 5,
    trace_name: str = "search_batch_executor",
    search_fn: Callable[..., Any] | None = None,
):
    run_search = search_fn or execute_perplexity_search

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
        iteration = int(state.get("consensus_iterations", 0))
        dimensions_run: list[str] = []

        try:
            for item in to_run:
                query = item.get("query", "")
                target_dimension = item.get("target_dimension", "narrative_framework")
                mode = item.get("mode", "exploratory")
                dimensions_run.append(target_dimension)

                evidence = run_search(
                    deps,
                    query=query,
                    mode=mode,
                    target_dimension=target_dimension,
                    ticker=ticker,
                )
                evidence_dict = evidence.model_dump()
                buffer.append(evidence_dict)
                pending.append(evidence_dict)

                record = record_from_evidence(
                    deps, evidence, iteration=iteration, mode=str(mode),
                )
                search_memory = append_search_record(search_memory, record)
                new_docs = _append_documents(new_docs, evidence.doc_ids)
                api_calls += 1

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
            updates.update(deps.trace({**state, **updates}, trace_name, {
                "batch_size": len(to_run),
                "dimensions": dimensions_run,
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
