"""Human review node for research subgraphs."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile


def _human_review_config(deps: EquityResearchDeps, task_profile: TaskProfile) -> dict[str, Any]:
    er = deps.config.get("equity_research", {})
    defaults = {"enabled": False, "interrupt": False}
    key = f"{task_profile.task_id}_human_review"
    return {**defaults, **(er.get(key) or er.get("consensus_human_review") or {})}


def create_human_review_node(deps: EquityResearchDeps, task_profile: TaskProfile):
    def human_review(state: dict[str, Any]) -> dict[str, Any]:
        config = _human_review_config(deps, task_profile)
        followup = str(state.get("human_followup_query") or "").strip()
        history = list(state.get("human_followup_history", []))
        coverage = dict(state.get("coverage_report") or {})

        payload = {
            "report_excerpt": str(state.get("final_report", ""))[:1500],
            "coverage_gaps": coverage.get("critical_gaps", []),
            "overall_score": coverage.get("overall_score", 0.0),
            "awaiting_followup": bool(config.get("enabled")) and not followup,
        }

        updates: dict[str, Any] = {"human_review_payload": payload}

        if followup:
            history.append(followup)
            coverage["routing_decision"] = "continue"
            updates.update({
                "human_followup_history": history,
                "human_followup_query": "",
                "_pending_human_followup": True,
                "coverage_report": coverage,
            })
        else:
            updates["_pending_human_followup"] = False

        updates.update(deps.trace({**state, **updates}, f"{task_profile.task_id}_human_review", {
            "has_followup": bool(followup),
            "enabled": config.get("enabled", False),
        }))
        return updates

    return human_review
