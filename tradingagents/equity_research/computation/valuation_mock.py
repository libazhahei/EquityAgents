"""Mock PE/EV valuation for equity research."""

from __future__ import annotations

from typing import Any

from tradingagents.agents.schemas import PortfolioRating
from tradingagents.equity_research.state.schemas import ValuationMockResult
from tradingagents.equity_research.templates.report_template import get_investment_summary_template


def compute_valuation_mock(
    ticker: str,
    current_price: float,
    forecast_model: dict[str, Any] | None,
    facts: list[dict],
) -> ValuationMockResult:
    forecast_model = forecast_model or {}
    eps_forecast = forecast_model.get("eps_forecast_3y", [])
    forward_eps = eps_forecast[-1] if eps_forecast else 1.0

    peer_median_pe = _fact_value(facts, "trailing_pe") or 20.0
    implied_pe = peer_median_pe * 1.05
    target_price = round(forward_eps * implied_pe, 2)

    if current_price <= 0:
        current_price = target_price * 0.85

    upside = (target_price - current_price) / current_price
    rating = _rating_from_upside(upside)

    return ValuationMockResult(
        current_price=current_price,
        target_price=target_price,
        upside_pct=round(upside, 4),
        rating=rating,
        peer_median_pe=peer_median_pe,
        implied_pe=implied_pe,
        notes="Trading multiple valuation from forecast EPS and peer median P/E.",
        is_mock=True,
    )


def _fact_value(facts: list[dict], metric_name: str) -> float | None:
    for f in facts:
        if metric_name.lower() in f.get("metric_name", "").lower():
            val = f.get("metric_value")
            if val is not None:
                return float(val)
    return None


def _rating_from_upside(upside: float) -> PortfolioRating:
    thresholds = get_investment_summary_template().get("rating_thresholds", {})
    buy_min = thresholds.get("Buy", {}).get("min_upside_pct", 0.15)
    ow_min = thresholds.get("Overweight", {}).get("min_upside_pct", 0.10)
    sell_max = thresholds.get("Sell", {}).get("max_upside_pct", -0.10)
    if upside >= buy_min:
        return PortfolioRating.BUY
    if upside >= ow_min:
        return PortfolioRating.OVERWEIGHT
    if upside >= sell_max:
        return PortfolioRating.HOLD
    if upside >= -0.05:
        return PortfolioRating.UNDERPERFORM
    return PortfolioRating.SELL


def check_rating_upside_consistency(
    rating: str,
    upside: float,
    dividend_yield_pct: float = 0.0,
) -> list[str]:
    issues = []
    total_return = upside + dividend_yield_pct
    thresholds = get_investment_summary_template().get("rating_thresholds", {})
    buy_min = thresholds.get("Buy", {}).get("min_upside_pct", 0.15)
    ow_min = thresholds.get("Overweight", {}).get("min_upside_pct", 0.10)
    sell_max = thresholds.get("Sell", {}).get("max_upside_pct", -0.10)

    if rating in (PortfolioRating.BUY.value,) and total_return < buy_min:
        issues.append("rating_upside_mismatch")
    if rating == PortfolioRating.OVERWEIGHT.value and total_return < ow_min:
        issues.append("rating_upside_mismatch")
    if rating == PortfolioRating.SELL.value and total_return > sell_max:
        issues.append("rating_upside_mismatch")
    return issues
