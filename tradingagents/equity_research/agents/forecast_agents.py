"""Business driver, forecast, valuation, and chart agents."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.computation.forecast import build_simple_forecast
from tradingagents.equity_research.tools.calculators import calculate_trading_multiple_valuation
from tradingagents.equity_research.state.schemas import ChartPlaceholder, Claim, ClaimStatus, ClaimType, claim_to_dict


def create_forecast_assumptions(deps: EquityResearchDeps):
    def forecast_assumptions(state: dict[str, Any]) -> dict[str, Any]:
        facts = state.get("structured_facts", [])
        kpis = state.get("operating_kpis", {})
        prompt = (
            f"Decompose forecast assumptions for {state['ticker']} from facts and KPIs:\n"
            f"Facts: {json.dumps(facts[:15], default=str)}\n"
            f"KPIs: {json.dumps(kpis, default=str)}\n"
            f"Drivers: {json.dumps(state.get('business_drivers', []), default=str)}\n"
            "Return JSON array with driver_name, segment, impact, metric_link, assumption."
        )
        response = deps.quick_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        drivers = _parse_json_array(text)
        if not drivers:
            drivers = [
                {"driver_name": "core_revenue", "segment": "total", "impact": "high", "metric_link": "revenue"},
                {"driver_name": "operating_margin", "segment": "total", "impact": "medium", "metric_link": "margin"},
            ]
        assumptions = [
            {
                "assumption_id": f"asm_{uuid.uuid4().hex[:8]}",
                "metric": d.get("metric_link", "revenue"),
                "our_assumption": d.get("assumption", d.get("driver_name", "")),
                "rationale": d.get("driver_name", ""),
                "used_in": ["financial_forecast"],
            }
            for d in drivers
        ]
        updates = {
            "business_drivers": drivers,
            "model_assumptions": assumptions,
            "active_section_id": "6_earnings_forecast",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "forecast_assumptions"))
        return updates

    return forecast_assumptions


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
            section_id="6_earnings_forecast",
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
            "model_assumptions": model.get("assumptions", state.get("model_assumptions", [])),
            "claims": claims,
            "active_section_id": "6_earnings_forecast",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "financial_forecast"))
        return updates

    return financial_forecast


def create_valuation_engine(deps: EquityResearchDeps):
    def valuation(state: dict[str, Any]) -> dict[str, Any]:
        result = calculate_trading_multiple_valuation(
            ticker=state["ticker"],
            current_price=float(state.get("current_price") or 0),
            forecast_model=state.get("forecast_model"),
            facts=state.get("structured_facts", []),
        )
        claim = Claim(
            claim_id=str(uuid.uuid4()),
            hypothesis_id="valuation",
            section_id="7_valuation",
            claim_type=ClaimType.VALUATION,
            text=f"Valuation target {result.get('target_price')} ({result.get('rating')})",
            status=ClaimStatus.VERIFIED,
            confidence=0.7,
            supporting_computation_ids=["valuation_engine"],
        )
        claims = list(state.get("claims", []))
        claims.append(claim_to_dict(claim))
        updates = {
            "valuation_method": result.get("method", "pe_ev_multiples"),
            "valuation_model": result,
            "target_price": result.get("target_price"),
            "rating": result.get("rating"),
            "claims": claims,
            "active_section_id": "7_valuation",
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "valuation"))
        return updates

    return valuation


# Backward-compatible alias
create_valuation_mock = create_valuation_engine
create_business_driver_decomp = create_forecast_assumptions


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
        scenario = state.get("scenario_analysis", {})
        if scenario.get("valuation_sensitivity_table"):
            placeholders.append({
                "chart_id": str(uuid.uuid4()),
                "title": f"{state['ticker']} Valuation Sensitivity",
                "time_range": "Bull/Base/Bear",
                "data_source": "scenario_sensitivity",
                "processing_method": "multiple scenario target prices",
            })
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
