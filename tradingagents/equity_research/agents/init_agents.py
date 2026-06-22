"""Initialization and template agents."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import yfinance as yf

from tradingagents.agents.utils.agent_utils import build_instrument_context, resolve_instrument_identity
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.schemas import ResearchBudget
from tradingagents.equity_research.templates.report_template import (
    get_mvp1_template_list,
    section_coverage_entry,
)


def create_initialize_state(deps: EquityResearchDeps):
    def initialize_state(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state.get("ticker", "").upper()
        identity = resolve_instrument_identity(ticker)
        instrument_context = build_instrument_context(ticker, "stock", identity)
        report_id = state.get("report_id") or str(uuid.uuid4())
        er_cfg = deps.config.get("equity_research", {})
        current_price = 0.0
        currency = "USD"
        try:
            info = yf.Ticker(ticker).info
            current_price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0)
            currency = info.get("currency", "USD")
        except Exception:
            pass
        budget = ResearchBudget(
            max_search_queries=er_cfg.get("budget", {}).get("max_search_queries", 5),
            max_extraction_docs=er_cfg.get("budget", {}).get("max_extraction_docs", 8),
            max_hypothesis_iterations=er_cfg.get("max_hypothesis_iterations", 3),
        )
        deps.redis.budget_init(report_id, {
            "search_queries": budget.max_search_queries,
            "extraction_docs": budget.max_extraction_docs,
        })
        updates = {
            "report_id": report_id,
            "company_name": identity.get("name", ticker),
            "sector": identity.get("sector", ""),
            "industry": identity.get("industry", ""),
            "instrument_context": instrument_context,
            "current_price": current_price,
            "currency": currency,
            "report_type": state.get("report_type") or er_cfg.get("report_type", "initiation"),
            "time_horizon": state.get("time_horizon") or er_cfg.get("time_horizon", "12m"),
            "research_budget": budget.model_dump(),
            "started_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "initialize_state", {"ticker": ticker}))
        return updates

    return initialize_state


def create_load_report_template(deps: EquityResearchDeps):
    def load_report_template(state: dict[str, Any]) -> dict[str, Any]:
        template = get_mvp1_template_list()
        coverage = {s["section_id"]: section_coverage_entry(s["section_id"]) for s in template}
        updates = {
            "report_template": template,
            "section_coverage": coverage,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "load_report_template"))
        return updates

    return load_report_template
