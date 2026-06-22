"""Risk mapping workflow — risk-to-thesis and catalyst calendar."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.workflow_agents import (
    create_catalyst_monitor,
    create_risk_to_thesis_mapping,
)
from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy


def create_risk_mapping(deps: EquityResearchDeps):
    _risk = create_risk_to_thesis_mapping(deps)
    _catalyst = create_catalyst_monitor(deps)

    def risk_mapping(state: dict[str, Any]) -> dict[str, Any]:
        working = dict(state)
        working.update(_risk(working))
        working.update(_catalyst(working))
        working.update(sync_ledgers_from_legacy(working))
        working["last_updated"] = datetime.utcnow().isoformat()
        working.update(deps.trace(working, "risk_mapping"))
        return working

    return risk_mapping
