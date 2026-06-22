"""Modeling workflow — historical financials through forecast consistency gate."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.forecast_agents import (
    create_financial_forecast,
    create_forecast_assumptions,
)
from tradingagents.equity_research.agents.workflow_agents import (
    create_forecast_consistency_check,
    create_historical_financials,
    create_operating_kpi_extraction,
)
from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy


def create_modeling_workflow(deps: EquityResearchDeps):
    _historical = create_historical_financials(deps)
    _kpi = create_operating_kpi_extraction(deps)
    _assumptions = create_forecast_assumptions(deps)
    _forecast = create_financial_forecast(deps)
    _consistency = create_forecast_consistency_check(deps)

    def modeling_workflow(state: dict[str, Any]) -> dict[str, Any]:
        working = dict(state)
        working.update(_historical(working))
        working.update(_kpi(working))
        working.update(_assumptions(working))
        working.update(_forecast(working))
        working.update(_consistency(working))
        working.update(sync_ledgers_from_legacy(working))
        working["last_updated"] = datetime.utcnow().isoformat()
        working.update(deps.trace(working, "modeling_workflow", {"route": working.get("next_route")}))
        return working

    return modeling_workflow
