"""Business driver, forecast, valuation mock, and chart placeholder agents."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from tradingagents.agents.schemas import PortfolioRating
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.computation.forecast import build_simple_forecast
from tradingagents.equity_research.computation.valuation_mock import compute_valuation_mock
from tradingagents.equity_research.state.schemas import ChartPlaceholder, Claim, ClaimStatus, ClaimType, claim_to_dict


def create_business_driver_decomp(deps: EquityResearchDeps):
    def business_driver_decomp(state: dict[str, Any]) -> dict[str, Any]:
        facts = state.get("structured_facts", [])
        prompt = (
            f"Decompose business drivers for {state['ticker']} from facts:\n"
            f"{json.dumps(facts[:15], default=str)}\n"
            f"Instrument: {state.get('instrument_context', '')[:1000]}\n"
            "Return JSON array with driver_name, segment, impact, metric_link."
        )
        response = deps.quick_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        drivers = _parse_json_array(text)
        if not drivers:
            drivers = [
                {"driver_name": "core_revenue", "segment": "total", "impact": "high", "metric_link": "revenue"},
                {"driver_name": "operating_margin", "segment": "total", "impact": "medium", "metric_link": "margin"},
            ]
        updates = {
            "business_drivers": drivers,
            "active_section_id": "5_earnings_forecast",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "business_driver_decomp"))
        return updates

    return business_driver_decomp


def create_financial_forecast(deps: EquityResearchDeps):
    def financial_forecast(state: dict[str, Any]) -> dict[str, Any]:
        model = build_simple_forecast(
            ticker=state["ticker"],
            facts=state.get("structured_facts", []),
            drivers=state.get("business_drivers", []),
            llm=deps.quick_llm,
        )
        claim = Claim(
            claim_id=str(uuid.uuid4()),
            hypothesis_id="forecast",
            section_id="5_earnings_forecast",
            claim_type=ClaimType.FORECAST,
            text=f"EPS forecast: {model.get('eps_forecast_3y', [])}",
            status=ClaimStatus.VERIFIED,
            confidence=0.7,
            supporting_computation_ids=[model.get("computation_id", "")],
        )
        claims = list(state.get("claims", []))
        claims.append(claim_to_dict(claim))
        updates = {
            "forecast_model": model,
            "model_assumptions": model.get("assumptions", []),
            "claims": claims,
            "active_section_id": "5_earnings_forecast",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "financial_forecast"))
        return updates

    return financial_forecast


def create_valuation_mock(deps: EquityResearchDeps):
    def valuation_mock(state: dict[str, Any]) -> dict[str, Any]:
        result = compute_valuation_mock(
            ticker=state["ticker"],
            current_price=float(state.get("current_price") or 0),
            forecast_model=state.get("forecast_model"),
            facts=state.get("structured_facts", []),
        )
        claim = Claim(
            claim_id=str(uuid.uuid4()),
            hypothesis_id="valuation",
            section_id="6_valuation",
            claim_type=ClaimType.VALUATION,
            text=f"Mock valuation target {result.target_price} ({result.rating.value})",
            status=ClaimStatus.VERIFIED,
            confidence=0.6,
            supporting_computation_ids=["valuation_mock"],
        )
        claims = list(state.get("claims", []))
        claims.append(claim_to_dict(claim))
        updates = {
            "valuation_method": result.method,
            "valuation_model": result.model_dump(),
            "target_price": result.target_price,
            "rating": result.rating.value,
            "claims": claims,
            "active_section_id": "6_valuation",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "valuation_mock"))
        return updates

    return valuation_mock


def create_chart_generation(deps: EquityResearchDeps):
    def chart_generation(state: dict[str, Any]) -> dict[str, Any]:
        forecast = state.get("forecast_model") or {}
        placeholders = [
            ChartPlaceholder(
                chart_id=str(uuid.uuid4()),
                title=f"{state['ticker']} EPS Forecast (3Y)",
                time_range="FY+1 to FY+3",
                x_axis="Fiscal Year",
                y_axis="EPS (USD)",
                data_source="financial_forecast agent / structured_facts",
                processing_method="LLM-assisted growth assumptions applied to base EPS",
            ).model_dump(),
            ChartPlaceholder(
                chart_id=str(uuid.uuid4()),
                title=f"{state['ticker']} Revenue Trend",
                time_range="Historical 3Y + Forecast 3Y",
                x_axis="Fiscal Year",
                y_axis="Revenue (USD millions)",
                data_source="yfinance fundamentals + forecast_model",
                processing_method="YoY growth extrapolation from business drivers",
            ).model_dump(),
        ]
        if forecast.get("eps_forecast_3y"):
            placeholders[0]["notes"] = f"Data points: {forecast['eps_forecast_3y']}"
        updates = {
            "chart_placeholders": placeholders,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "chart_generation"))
        return updates

    return chart_generation


def _parse_json_array(text: str) -> list:
    import re

    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        pass
    return []
