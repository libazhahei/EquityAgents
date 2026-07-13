"""Finalizer node — generates final_report from structured_view."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm


def _build_unavailable_data_disclosure(state: dict[str, Any], view: Any) -> str:
    notes: list[str] = []
    answer_cards = getattr(view, "answer_cards", None)
    if not answer_cards:
        return ""
    for qid, card in answer_cards.items():
        data_notes = getattr(card, "data_availability_notes", None)
        if not data_notes:
            continue
        for note in data_notes:
            if note.status != "unavailable":
                continue
            attempted = ", ".join(note.attempted_sources[:5]) if note.attempted_sources else "n/a"
            notes.append(
                f"- {qid} / {note.metric}: unavailable; attempted={attempted}; "
                f"rationale={note.rationale or 'not provided'}; proxy={note.proxy_metric or 'none'}"
            )
    if not notes:
        return ""
    lines = [
        "## Data Availability Limitations",
        "The following required data could not be obtained after retry and affects confidence:",
        *notes[:20],
    ]
    unresolved = state.get("unresolved_gaps") or []
    if unresolved:
        lines.append("")
        lines.append("Remaining unresolved gaps:")
        lines.extend(f"- {g}" for g in unresolved[:20])
    return "\n".join(lines)


def _finalize_section_research_report(
    deps: EquityResearchDeps,
    state: dict[str, Any],
    llm_report: str,
) -> tuple[str, str]:
    """Assemble complete report: LLM narrative (root + subs) + appendix + merged refs."""
    del deps  # reserved for future compact/config hooks
    from tradingagents.equity_research.tasks.section_research.articles import (
        assemble_final_report,
    )
    from tradingagents.equity_research.tools.findings_cache_tools import (
        resolve_section_artifact_dir,
        section_run_dir,
    )

    artifact_dir = state.get("section_artifact_dir") or str(resolve_section_artifact_dir(state))
    report, _refs = assemble_final_report(
        llm_report=llm_report,
        artifact_dir=artifact_dir,
        include_article_appendix=True,
    )
    out_dir = Path(artifact_dir).parent
    report_path = out_dir / "final_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    narrative_path = out_dir / "section_narrative.md"
    narrative_path.write_text(llm_report.strip() + "\n", encoding="utf-8")
    section_run_dir(str(state.get("ticker") or ""), str(state.get("section_id") or "")).mkdir(
        parents=True, exist_ok=True,
    )
    return report, str(report_path)


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
            assert task_profile.build_finalizer_prompt is not None
            prompt = task_profile.build_finalizer_prompt(deps, ctx)

            report = ""
            try:
                response = resolve_research_llm(deps, "quick").invoke(prompt)
                report = response.content if hasattr(response, "content") else str(response)
                report = str(report).strip()
            except Exception:
                report = view.to_legacy_summary()
                assumptions = state.get("assumptions") or {}
                if assumptions:
                    report += "\n\n## Key Assumptions Behind Consensus\n"
                    report += str(assumptions)
                compliance_flags = state.get("compliance_flags", [])
                if compliance_flags:
                    report += "\n\n## Compliance Flags\n"
                    report += "\n".join(
                        f"- [{f.get('type', 'flag')}] {f.get('message', '')}"
                        for f in compliance_flags[:10]
                    )

            disclosure = _build_unavailable_data_disclosure(state, view)
            if disclosure and "## Data Availability Limitations" not in report:
                report = f"{report}\n\n{disclosure}".strip()

            updates: dict[str, Any] = {}
            if task_profile.task_id == "section_research":
                llm_report = report
                full_report, report_path = _finalize_section_research_report(
                    deps, state, llm_report,
                )
                updates = {
                    "final_report": full_report,
                    "consensus_report": full_report,
                    "executive_summary": llm_report,
                    "final_report_path": report_path,
                    "section_artifact_dir": state.get("section_artifact_dir")
                    or str(Path(report_path).parent / "articles"),
                }
            else:
                updates = {
                    "final_report": report,
                    "consensus_report": report,
                }

            updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_finalizer", {
                "iterations": state.get("iterations", 0),
                "evidence_count": len(state.get("evidence_buffer", [])),
                "report_chars": len(str(updates.get("final_report", ""))),
            }))
            return updates
        except Exception as exc:
            errors.append(f"finalizer: {exc}")
            return {"errors": errors, "final_report": ""}

    return finalizer
