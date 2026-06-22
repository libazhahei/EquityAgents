"""Final QA workflow — consistency and compliance checks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.workflow_agents import (
    create_compliance_check,
    create_final_consistency_check,
)
from tradingagents.equity_research.state.ledgers import IssueLedgerEntry, sync_ledgers_from_legacy


def create_final_qa(deps: EquityResearchDeps):
    _consistency = create_final_consistency_check(deps)
    _compliance = create_compliance_check(deps)

    def final_qa(state: dict[str, Any]) -> dict[str, Any]:
        working = dict(state)
        working.update(_consistency(working))
        working.update(_compliance(working))

        issue_ledger = list(working.get("issue_ledger", []))
        for finding in working.get("review_findings", []):
            if isinstance(finding, str):
                issue_ledger.append(IssueLedgerEntry(
                    issue_id=f"qa_{finding}",
                    gate="final_qa",
                    message=finding,
                ).model_dump())

        route = working.get("next_route", "pass")
        if working.get("compliance_flags") and route == "pass":
            route = "pass"
        working["next_route"] = route
        working["issue_ledger"] = issue_ledger
        working.update(sync_ledgers_from_legacy(working))
        working["last_updated"] = datetime.utcnow().isoformat()
        working.update(deps.trace(working, "final_qa", {"route": route}))
        return working

    return final_qa
