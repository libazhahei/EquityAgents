"""Valuation workflow — valuation, scenario, rating check."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.forecast_agents import create_valuation_engine
from tradingagents.equity_research.agents.workflow_agents import (
    create_rating_target_price_check,
    create_scenario_sensitivity,
)
from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy, ValuationLedgerEntry


def create_valuation_workflow(deps: EquityResearchDeps):
    _valuation = create_valuation_engine(deps)
    _scenario = create_scenario_sensitivity(deps)
    _rating = create_rating_target_price_check(deps)

    def valuation_workflow(state: dict[str, Any]) -> dict[str, Any]:
        working = dict(state)
        working.update(_valuation(working))
        working.update(_scenario(working))
        working.update(_rating(working))

        valuation_ledger = list(working.get("valuation_ledger", []))
        if working.get("valuation_model"):
            vm = working["valuation_model"]
            entry = ValuationLedgerEntry(
                valuation_id=f"val_{len(valuation_ledger)}",
                version=len(valuation_ledger) + 1,
                method=working.get("valuation_method", "trading_multiple"),
                target_price=vm.get("target_price"),
                rating=vm.get("rating", ""),
            ).model_dump()
            valuation_ledger.append(entry)
            working["valuation_ledger"] = valuation_ledger

        working.update(sync_ledgers_from_legacy(working))
        working["last_updated"] = datetime.utcnow().isoformat()
        working.update(deps.trace(working, "valuation_workflow", {"route": working.get("next_route")}))
        return working

    return valuation_workflow
