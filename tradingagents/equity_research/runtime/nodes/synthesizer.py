"""Synthesizer node — merges evidence into structured_view."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def create_synthesizer_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    def synthesizer(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            raw_view = state.get("structured_view") or state.get("consensus_view") or {}
            if raw_view:
                view = task_profile.output_schema.model_validate(raw_view)
            else:
                view = task_profile.empty_view_fn(ticker)

            pending = state.get("pending_evidence", [])
            if not pending:
                return {"structured_view": view.model_dump(), "pending_evidence": []}

            prompt = task_profile.build_synthesizer_prompt(deps, state, view, pending)

            def _fallback():
                return task_profile.view_update_schema(ticker=ticker)

            try:
                update = invoke_structured_with_retry(
                    deps.quick_llm,
                    task_profile.view_update_schema,
                    prompt,
                    agent_name=f"{task_profile.task_id}_synthesizer",
                    max_attempts=_max_retries(deps),
                    fallback=_fallback,
                )
                update_dump = update.model_dump(exclude_unset=True)
                if update_dump:
                    view = task_profile.merge_view_fn(view, update)
                elif task_profile.apply_evidence_heuristic_fn:
                    task_profile.apply_evidence_heuristic_fn(view, pending)
            except StructuredOutputUnsupported:
                if task_profile.apply_evidence_heuristic_fn:
                    task_profile.apply_evidence_heuristic_fn(view, pending)

            if task_profile.preserve_citations_fn:
                task_profile.preserve_citations_fn(view, pending)
            memory_fn = task_profile.extra_config.get("preserve_memory_citations_fn")
            search_memory = state.get("search_memory", [])
            if memory_fn and search_memory:
                memory_fn(view, search_memory)

            updates: dict[str, Any] = {
                "structured_view": view.model_dump(),
                "pending_evidence": [],
            }
            if task_profile.task_id == "consensus":
                updates["consensus_view"] = view.model_dump()
            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_synthesizer"))
            return updates
        except Exception as exc:
            errors.append(f"synthesizer: {exc}")
            return {"errors": errors}

    return synthesizer
