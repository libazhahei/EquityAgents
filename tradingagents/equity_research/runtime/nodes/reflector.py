"""Reflector node — coverage evaluation and exploration graph update."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.exploration_graph import ExplorationGraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.runtime.utils.reflector_routing import (
    TERMINAL_LIMITED_GAP_LABELS,
    should_force_exit_on_terminal_gaps,
)
from tradingagents.equity_research.runtime.utils.search_memory import build_search_memory_for_prompt
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.state.blackboard import (
    BlackboardEntry,
    extract_tags_from_text,
)


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _extract_blackboard_entries_from_coverage(
    state: dict[str, Any],
    report: Any,
    iteration: int,
) -> list[dict]:
    """Extract blackboard entries from coverage report insights.

    The reflector identifies critical gaps, contradictions, and cross-dimension
    insights during coverage evaluation. These are valuable for other nodes
    (planner, executor) to know about.
    """
    entries: list[dict] = []
    section_id = state.get("section_id", "")

    # Extract entries from critical_gaps
    critical_gaps = getattr(report, "critical_gaps", []) or []
    for gap in critical_gaps:
        if isinstance(gap, dict):
            gap_text = gap.get("description") or gap.get("gap") or str(gap)
            gap_label = gap.get("label") or gap.get("dimension") or ""
        else:
            gap_text = str(gap)
            gap_label = ""

        if not gap_text or len(gap_text) < 10:
            continue

        content = f"Critical gap: {gap_text}"
        if gap_label:
            content = f"[{gap_label}] {content}"

        tags = extract_tags_from_text(gap_text)
        if gap_label:
            tags = list(dict.fromkeys(tags + [gap_label.lower().replace(" ", "_")]))

        entry = BlackboardEntry(
            section_id=section_id,
            source_node="reflector",
            entry_type="methodology",
            content=content[:300],
            tags=tags[:5],
            confidence=0.6,
            created_at_iteration=iteration,
        )
        entries.append(entry.model_dump())

    # Extract entries from suggested_focus (potential hypotheses)
    suggested_focus = getattr(report, "suggested_focus", "") or ""
    if suggested_focus and len(suggested_focus) > 20:
        tags = extract_tags_from_text(suggested_focus)
        entry = BlackboardEntry(
            section_id=section_id,
            source_node="reflector",
            entry_type="hypothesis",
            content=f"Reflector suggests: {suggested_focus}"[:300],
            tags=tags[:5],
            confidence=0.4,
            created_at_iteration=iteration,
        )
        entries.append(entry.model_dump())

    # Extract entries from dimension_scores with low coverage (contradictions/findings)
    dimension_scores = getattr(report, "dimension_scores", {}) or {}
    if isinstance(dimension_scores, dict):
        for dim_name, dim_data in dimension_scores.items():
            if isinstance(dim_data, dict):
                score = float(dim_data.get("score", 1.0))
                notes = dim_data.get("notes") or dim_data.get("gaps") or ""
            else:
                score = float(dim_data) if dim_data else 1.0
                notes = ""

            # Low coverage dimensions may indicate contradictions or data issues
            if score < 0.4 and notes:
                tags = extract_tags_from_text(f"{dim_name} {notes}")
                entry = BlackboardEntry(
                    section_id=section_id,
                    source_node="reflector",
                    entry_type="contradiction" if score < 0.2 else "finding",
                    content=f"Low coverage on {dim_name}: {notes}"[:300],
                    tags=tags[:5],
                    confidence=0.3,
                    created_at_iteration=iteration,
                )
                entries.append(entry.model_dump())

    return entries


def create_reflector_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    def reflector(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        iterations = int(state.get("iterations", state.get("consensus_iterations", 0))) + 1
        try:
            raw_view = state.get("structured_view") or state.get("consensus_view") or {}
            if raw_view:
                view = task_profile.output_schema.model_validate(raw_view)
            else:
                view = task_profile.empty_view_fn(state.get("ticker", ""))

            search_memory = state.get("search_memory", [])
            memory_summary = ""
            if search_memory:
                memory_summary = build_search_memory_for_prompt(
                    deps, search_memory, compact=False,
                )

            prompt = task_profile.build_reflector_prompt(deps, view, memory_summary)
            # Inject blackboard context for reflector
            if task_profile.task_id == "section_research":
                bb = state.get("blackboard") or []
                if bb:
                    bb_text = format_blackboard_for_prompt(bb, max_items=8, section_id=state.get("section_id"))
                    if bb_text:
                        prompt = prompt + "\n\n" + bb_text

            def _fallback():
                report = task_profile.default_coverage_report_fn(view)
                return task_profile.coverage_eval_schema(
                    dimension_scores=report.dimension_scores,
                    overall_score=report.overall_score,
                    critical_gaps=report.critical_gaps,
                    suggested_focus=report.suggested_focus,
                )

            try:
                evaluation = invoke_structured_with_retry(
                    resolve_research_llm(deps, "quick"),
                    task_profile.coverage_eval_schema,
                    prompt,
                    agent_name=f"{task_profile.task_id}_coverage_reflector",
                    max_attempts=_max_retries(deps),
                    fallback=_fallback,
                )
                report = task_profile.evaluation_to_report_fn(evaluation)
            except StructuredOutputUnsupported:
                report = task_profile.default_coverage_report_fn(view)

            post_fn = task_profile.extra_config.get("post_reflector_fn")
            if post_fn:
                report = post_fn(view, report)

            max_iter = int(state.get("max_iterations", state.get("max_consensus_iterations", task_profile.max_iterations)))
            force_exit_labels = task_profile.extra_config.get(
                "force_exit_gap_labels",
                TERMINAL_LIMITED_GAP_LABELS,
            )
            terminal_only_exit = should_force_exit_on_terminal_gaps(
                report,
                allowed=force_exit_labels,
            )
            if terminal_only_exit:
                report.routing_decision = "exit"
            elif report.overall_score >= task_profile.coverage_threshold and not report.critical_gaps:
                report.routing_decision = "exit"
            elif iterations >= max_iter:
                report.routing_decision = "exit"
            else:
                report.routing_decision = "continue"

            view.coverage_score = report.overall_score
            view.dimension_coverage = report.dimension_scores

            coverage_history = list(state.get("coverage_history", []))
            coverage_history.append(report.model_dump())

            graph = ExplorationGraph.from_dict(state.get("exploration_graph"))
            parent_id = state.get("current_node_id") or None
            if parent_id and parent_id not in graph.nodes:
                parent_id = graph.latest_node().node_id if graph.latest_node() else None
            node = graph.new_node(
                parent_id=parent_id,
                branch_id="main",
                query_plan=list(state.get("query_queue", [])),
                evidence=list(state.get("pending_evidence", [])) or list(state.get("evidence_buffer", []))[-5:],
                structured_view_snapshot=view.model_dump(),
                coverage_score=report.overall_score,
                routing_decision=report.routing_decision,
                iteration=iterations,
            )

            updates = {
                "coverage_report": report.model_dump(),
                "coverage_history": coverage_history,
                "structured_view": view.model_dump(),
                "consensus_view": view.model_dump(),
                "iterations": iterations,
                "consensus_iterations": iterations,
                "exploration_graph": graph.to_dict(),
                "current_node_id": node.node_id,
            }

            # Auto-write blackboard entries from coverage insights
            if task_profile.task_id == "section_research":
                bb_entries = _extract_blackboard_entries_from_coverage(state, report, iterations)
                if bb_entries:
                    updates["blackboard"] = bb_entries

            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_coverage_reflector", {
                "overall_score": report.overall_score,
                "routing": report.routing_decision,
            }))
            return updates
        except Exception as exc:
            print(f"Reflector node error: {exc}")
            errors.append(f"reflector: {exc}")
            return {
                "errors": errors,
                "iterations": iterations,
                "coverage_report": {"routing_decision": "exit"},
            }

    return reflector
