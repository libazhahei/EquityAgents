"""Finalizer node — generates final_report from structured_view."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile


def create_finalizer_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    def finalizer(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        ticker = state.get("ticker", "")
        try:
            raw_view = state.get("structured_view") or state.get("consensus_view") or {}
            if raw_view:
                view = task_profile.output_schema.model_validate(raw_view)
            else:
                view = task_profile.empty_view_fn(ticker)

            report_max_chars = int(
                deps.config.get("equity_research", {}).get(
                    "consensus_report_max_chars", task_profile.report_max_chars,
                )
            )
            ctx = {
                "state": state,
                "view": view,
                "assumptions": state.get("assumptions") or {},
                "coverage": state.get("coverage_report") or {},
                "search_memory": state.get("search_memory", []),
                "skill_ctx": state.get("active_skill_context", {}),
                "compliance_flags": state.get("compliance_flags", []),
                "report_max_chars": report_max_chars,
            }
            prompt = task_profile.build_finalizer_prompt(deps, ctx)

            report = ""
            try:
                response = deps.quick_llm.invoke(prompt)
                report = response.content if hasattr(response, "content") else str(response)
                report = str(report).strip()[:report_max_chars]
            except Exception:
                report = view.to_legacy_summary()
                assumptions = state.get("assumptions") or {}
                if assumptions:
                    report += "\n\n## Key Assumptions Behind Consensus\n"
                    report += str(assumptions)[:2000]
                compliance_flags = state.get("compliance_flags", [])
                if compliance_flags:
                    report += "\n\n## Compliance Flags\n"
                    report += "\n".join(
                        f"- [{f.get('type', 'flag')}] {f.get('message', '')}"
                        for f in compliance_flags[:10]
                    )

            updates: dict[str, Any] = {
                "final_report": report,
                "consensus_report": report,
            }
            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_finalizer", {
                "iterations": state.get("iterations", 0),
                "evidence_count": len(state.get("evidence_buffer", [])),
                "report_chars": len(report),
            }))
            return updates
        except Exception as exc:
            errors.append(f"finalizer: {exc}")
            return {"errors": errors, "final_report": ""}

    return finalizer
