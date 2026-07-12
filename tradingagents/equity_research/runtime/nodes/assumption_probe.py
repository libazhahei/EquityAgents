"""Assumption probe sub-chain nodes."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.nodes.executor import create_executor_node
from tradingagents.equity_research.runtime.nodes.planner import create_planner_node
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.runtime.utils.search_memory import (
    build_search_memory_for_prompt,
    format_search_memory,
)
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.state.consensus_schemas import QueryPlan
from tradingagents.equity_research.tasks.consensus.compliance import (
    check_assumption_evidence_compliance,
    filter_compliant_citations,
)
from tradingagents.equity_research.tasks.consensus.merge import dedupe_preserve_order


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def create_assumption_probe_gate(deps: EquityResearchDeps, task_profile: TaskProfile):
    def assumption_probe_gate(state: dict[str, Any]) -> dict[str, Any]:
        return {}

    return assumption_probe_gate


def create_assumption_query_planner(deps: EquityResearchDeps, task_profile: TaskProfile):
    from tradingagents.equity_research.runtime.utils.dedupe import similarity
    from tradingagents.equity_research.runtime.utils.structured_invoke import invoke_structured_with_retry
    from tradingagents.equity_research.state.consensus_schemas import QueryItem

    def assumption_query_planner(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            prompt = task_profile.build_assumption_planner_prompt(deps, state)
            plan = invoke_structured_with_retry(
                resolve_research_llm(deps, "deep"),
                QueryPlan,
                prompt,
                agent_name="assumption_query_planner",
                max_attempts=_max_retries(deps),
                fallback=lambda: QueryPlan(queries=[]),
            )
            normalize_fn = task_profile.normalize_assumption_queries_fn or task_profile.normalize_queries_fn
            new_items = normalize_fn(plan.queries, ticker, True)[:5]
            executed = state.get("executed_queries", [])
            filtered = [
                item for item in new_items
                if not any(similarity(item.query, prev) > 0.7 for prev in executed)
            ]
            updates: dict[str, Any] = {"query_queue": [q.model_dump() for q in filtered]}
            updates.update(deps.trace({**state, **updates}, "assumption_query_planner"))
            return updates
        except Exception as exc:
            errors.append(f"assumption_query_planner: {exc}")
            return {"errors": errors}

    return assumption_query_planner


def create_assumption_batch_executor(deps: EquityResearchDeps, task_profile: TaskProfile):
    base_executor = create_executor_node(
        deps, task_profile, batch_size=5, trace_name="assumption_probe_executor",
    )

    def assumption_batch_executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base_executor(state)
        if not result:
            return {"assumption_pending_evidence": list(state.get("pending_evidence", []))}

        pending = list(result.get("pending_evidence", []))
        flags = list(state.get("compliance_flags", []))
        cleaned_pending: list[dict] = []

        for item in pending:
            item_dict = dict(item)
            citations = list(item_dict.get("citations") or [])
            kept, item_flags = filter_compliant_citations(citations, config=deps.config)
            item_dict["citations"] = kept
            item_dict["compliance_checked"] = True
            cleaned_pending.append(item_dict)
            flags.extend(item_flags)

        result["pending_evidence"] = cleaned_pending
        result["assumption_pending_evidence"] = cleaned_pending
        result["compliance_flags"] = flags
        return result

    return assumption_batch_executor


def create_assumption_synthesizer(deps: EquityResearchDeps, task_profile: TaskProfile):
    def assumption_synthesizer(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        pending = list(
            state.get("assumption_pending_evidence") or state.get("pending_evidence", [])
        )
        try:
            raw_view = state.get("structured_view") or state.get("consensus_view") or {}
            if raw_view:
                view = task_profile.output_schema.model_validate(raw_view)
            else:
                view = task_profile.empty_view_fn(ticker)

            assumptions_schema = task_profile.assumption_schema
            assumptions = assumptions_schema() if assumptions_schema else {}

            if pending and assumptions_schema:
                evidence_text = build_search_memory_for_prompt(deps, pending, max_chars=None)
                if not evidence_text or evidence_text == "- No prior searches recorded.":
                    evidence_text = format_search_memory(pending)

                prompt = task_profile.build_assumption_synth_prompt(deps, view, evidence_text)

                def _fallback():
                    return assumptions_schema(
                        business_model=view.narrative_framework.bull_case[:500],
                        key_debates=list(view.narrative_framework.key_debates),
                        sources=dedupe_preserve_order(
                            sum((ev.get("citations") or [] for ev in pending), [])
                        ),
                    )

                try:
                    assumptions = invoke_structured_with_retry(
                        resolve_research_llm(deps, "quick"),
                        assumptions_schema,
                        prompt,
                        agent_name="assumption_synthesizer",
                        max_attempts=_max_retries(deps),
                        fallback=_fallback,
                    )
                except StructuredOutputUnsupported:
                    assumptions = _fallback()

            assumptions_dict = (
                assumptions.model_dump() if hasattr(assumptions, "model_dump") else assumptions
            )
            flags = list(state.get("compliance_flags", []))
            flags.extend(
                check_assumption_evidence_compliance(
                    pending, assumptions_dict, config=deps.config,
                )
            )

            updates: dict[str, Any] = {
                "assumptions": assumptions_dict,
                "consensus_assumptions": assumptions_dict,
                "assumption_probe_completed": True,
                "assumption_pending_evidence": [],
                "pending_evidence": [],
                "compliance_flags": flags,
            }
            updates.update(deps.trace({**state, **updates}, "assumption_synthesizer"))
            return updates
        except Exception as exc:
            errors.append(f"assumption_synthesizer: {exc}")
            return {
                "errors": errors,
                "assumption_probe_completed": True,
                "assumption_pending_evidence": [],
            }

    return assumption_synthesizer


def create_assumption_compliance_check(deps: EquityResearchDeps, task_profile: TaskProfile):
    def assumption_compliance_check(state: dict[str, Any]) -> dict[str, Any]:
        pending = list(
            state.get("assumption_pending_evidence") or state.get("pending_evidence", [])
        )
        assumptions = state.get("assumptions") or {}
        flags = list(state.get("compliance_flags", []))
        flags.extend(
            check_assumption_evidence_compliance(pending, assumptions, config=deps.config)
        )
        updates = {"compliance_flags": flags}
        updates.update(deps.trace({**state, **updates}, "assumption_compliance_check"))
        return updates

    return assumption_compliance_check
