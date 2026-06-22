"""Mock PE/EV valuation for MVP1."""

from __future__ import annotations

from typing import Any

from tradingagents.agents.schemas import PortfolioRating
from tradingagents.equity_research.state.schemas import ValuationMockResult


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
        notes="MVP1 mock PE multiple valuation — not a DCF model.",
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
    if upside >= 0.15:
        return PortfolioRating.BUY
    if upside >= 0.10:
        return PortfolioRating.OVERWEIGHT
    if upside >= -0.05:
        return PortfolioRating.HOLD
    if upside >= -0.10:
        return PortfolioRating.UNDERWEIGHT
    return PortfolioRating.SELL


def check_rating_upside_consistency(rating: str, upside: float) -> list[str]:
    issues = []
    thresholds = {
        PortfolioRating.BUY.value: 0.15,
        PortfolioRating.OVERWEIGHT.value: 0.10,
        PortfolioRating.HOLD.value: -0.10,
        PortfolioRating.UNDERWEIGHT.value: -0.05,
        PortfolioRating.SELL.value: -0.10,
    }
    min_up = thresholds.get(rating)
    if min_up is not None and rating in (PortfolioRating.BUY.value, PortfolioRating.OVERWEIGHT.value):
        if upside < min_up:
            issues.append("rating_upside_mismatch")
    if rating == PortfolioRating.SELL.value and upside > -0.10:
        issues.append("rating_upside_mismatch")
    return issues
