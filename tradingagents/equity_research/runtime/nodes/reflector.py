"""Reflector node — coverage evaluation and exploration graph update."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.exploration_graph import ExplorationGraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.search_memory import build_search_memory_for_prompt
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


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
                memory_summary = (
                    f"\nSearch history summary:\n"
                    f"{build_search_memory_for_prompt(deps, search_memory)}\n"
                )

            prompt = task_profile.build_reflector_prompt(deps, view, memory_summary)

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
                    deps.quick_llm,
                    task_profile.coverage_eval_schema,
                    prompt,
                    agent_name=f"{task_profile.task_id}_coverage_reflector",
                    max_attempts=_max_retries(deps),
                    fallback=_fallback,
                )
                report = task_profile.evaluation_to_report_fn(evaluation)
            except StructuredOutputUnsupported:
                report = task_profile.default_coverage_report_fn(view)

            max_iter = int(state.get("max_iterations", state.get("max_consensus_iterations", task_profile.max_iterations)))
            if report.overall_score >= task_profile.coverage_threshold and not report.critical_gaps:
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
            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_coverage_reflector", {
                "overall_score": report.overall_score,
                "routing": report.routing_decision,
            }))
            return updates
        except Exception as exc:
            errors.append(f"reflector: {exc}")
            return {
                "errors": errors,
                "iterations": iterations,
                "coverage_report": {"routing_decision": "exit"},
            }

    return reflector
