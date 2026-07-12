"""Synthesizer node — merges evidence into structured_view."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.state.blackboard import (
    BlackboardEntry,
    extract_tags_from_text,
)
from tradingagents.equity_research.tasks.section_research.merge import (
    collect_evidence_for_question,
    enforce_structured_answer_requirements,
)


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _extract_blackboard_entries_from_evidence(
    state: dict[str, Any],
    pending: list[dict],
    iteration: int,
) -> list[dict]:
    """Extract blackboard entries from evidence that may be useful across questions.

    After merging evidence into structured_view, some evidence may contain
    interesting findings that don't fit neatly into the current dimension/question
    but could be valuable for other questions in the section.
    """
    entries: list[dict] = []
    section_id = state.get("section_id", "")
    active_task = state.get("active_task") or {}
    current_qid = str(active_task.get("question_id") or "")

    for ev in pending:
        if not isinstance(ev, dict):
            continue
        snippet = str(ev.get("snippet") or ev.get("quote") or ev.get("content") or "")
        if not snippet or len(snippet) < 20:
            continue

        # Check if evidence has cross-question potential
        # Evidence with broad findings or unexpected data points
        ev_qid = str(ev.get("question_id") or ev.get("target_dimension") or "")
        is_cross = ev_qid != current_qid and ev_qid != "general"

        # Determine entry type
        entry_type = "cross_question" if is_cross else "finding"

        # Extract tags from content
        tags = extract_tags_from_text(snippet)

        # Build content summary
        content = snippet[:300] if len(snippet) > 300 else snippet
        source = ev.get("source_type") or ev.get("source") or ""
        if source:
            content = f"{content} (source: {source})"

        entry = BlackboardEntry(
            section_id=section_id,
            question_id=current_qid or None,
            source_node="synthesizer",
            entry_type=entry_type,
            content=content,
            tags=tags,
            confidence=float(ev.get("reliability_score", 0.5)),
            created_at_iteration=iteration,
            related_evidence_ids=[str(ev.get("evidence_id", ""))] if ev.get("evidence_id") else [],
        )
        entries.append(entry.model_dump())

    return entries


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

            pending = list(state.get("pending_evidence", []))
            active_step = state.get("active_step") or {}
            force_synthesize = bool(
                state.get("_force_synthesize")
                or (active_step.get("action") or "").lower() == "synthesize"
            )
            if force_synthesize:
                active_task = state.get("active_task") or {}
                qid = str(active_task.get("question_id") or "general")
                aggregated = collect_evidence_for_question(state, qid)
                if aggregated:
                    pending = aggregated

            # Step 1: Always run heuristic (fast, deterministic merge)
            if pending and task_profile.apply_evidence_heuristic_fn:
                task_profile.apply_evidence_heuristic_fn(view, pending)

            # Step 2: LLM when pending evidence exists, or forced synthesize step
            should_call_llm = bool(pending) or force_synthesize
            if should_call_llm:
                prompt = task_profile.build_synthesizer_prompt(deps, state, view, pending)

                def _fallback():
                    return task_profile.view_update_schema(ticker=ticker)

                try:
                    update = invoke_structured_with_retry(
                        resolve_research_llm(deps, "quick"),
                        task_profile.view_update_schema,
                        prompt,
                        agent_name=f"{task_profile.task_id}_synthesizer",
                        max_attempts=_max_retries(deps),
                        fallback=_fallback,
                    )
                    update_dump = update.model_dump(exclude_unset=True)
                    if update_dump:
                        view = task_profile.merge_view_fn(view, update)
                except StructuredOutputUnsupported:
                    pass  # heuristic already handled evidence merge

            if task_profile.preserve_citations_fn:
                task_profile.preserve_citations_fn(view, pending)
            memory_fn = task_profile.extra_config.get("preserve_memory_citations_fn")
            search_memory = state.get("search_memory", [])
            if memory_fn and search_memory:
                memory_fn(view, search_memory)

            # Enforce structured quant/source constraints after merge so
            # downstream reflector/finalizer can reason over explicit gaps.
            enforcement_gaps: list[str] = []
            if task_profile.task_id == "section_research":
                enforcement_gaps = enforce_structured_answer_requirements(view)

            updates: dict[str, Any] = {
                "structured_view": view.model_dump(),
                "pending_evidence": [],
            }
            if force_synthesize:
                updates["_force_synthesize"] = False
            if enforcement_gaps:
                updates["unresolved_gaps"] = list(
                    dict.fromkeys([*(state.get("unresolved_gaps") or []), *enforcement_gaps])
                )
            if task_profile.task_id == "consensus":
                updates["consensus_view"] = view.model_dump()

            # Auto-write blackboard entries from evidence
            if pending and task_profile.task_id == "section_research":
                iteration = int(state.get("iterations", 0))
                bb_entries = _extract_blackboard_entries_from_evidence(state, pending, iteration)
                if bb_entries:
                    updates["blackboard"] = bb_entries

            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_synthesizer"))
            return updates
        except Exception as exc:
            errors.append(f"synthesizer: {exc}")
            return {"errors": errors}

    return synthesizer
