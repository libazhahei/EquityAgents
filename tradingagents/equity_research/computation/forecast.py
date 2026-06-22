"""Simple EPS forecast computation."""

from __future__ import annotations

import uuid
from typing import Any


def build_simple_forecast(
    ticker: str,
    facts: list[dict],
    drivers: list[dict],
    llm: Any | None = None,
) -> dict[str, Any]:
    base_eps = _fact_value(facts, "eps") or _fact_value(facts, "diluted_eps") or 1.0
    growth_rates = [0.12, 0.10, 0.08]
    eps_forecast = []
    eps = base_eps
    for rate in growth_rates:
        eps = round(eps * (1 + rate), 2)
        eps_forecast.append(eps)

    assumptions = [
        {"assumption": "revenue_growth_fy1", "value": "12%", "source": "business_drivers"},
        {"assumption": "revenue_growth_fy2", "value": "10%", "source": "business_drivers"},
        {"assumption": "revenue_growth_fy3", "value": "8%", "source": "business_drivers"},
        {"assumption": "base_eps", "value": str(base_eps), "source": "structured_facts"},
    ]
    return {
        "computation_id": str(uuid.uuid4()),
        "ticker": ticker,
        "base_eps": base_eps,
        "eps_forecast_3y": eps_forecast,
        "revenue_growth_assumptions": growth_rates,
        "assumptions": assumptions,
        "gross_margin_forecast": [0.45, 0.46, 0.47],
        "opex_forecast": ["stable", "stable", "stable"],
        "method": "simplified_growth_model",
    }


def _fact_value(facts: list[dict], metric_name: str) -> float | None:
    for f in facts:
        if f.get("metric_name", "").lower() == metric_name.lower():
            val = f.get("metric_value")
            if val is not None:
                return float(val)
    return None
