"""Unit tests for mock valuation and rating consistency."""

from tradingagents.agents.schemas import PortfolioRating
from tradingagents.equity_research.computation.valuation_mock import (
    check_rating_upside_consistency,
    compute_valuation_mock,
    _rating_from_upside,
)


def test_rating_from_upside_thresholds():
    assert _rating_from_upside(0.20) == PortfolioRating.BUY
    assert _rating_from_upside(0.12) == PortfolioRating.OVERWEIGHT
    assert _rating_from_upside(0.0) == PortfolioRating.HOLD
    assert _rating_from_upside(-0.08) == PortfolioRating.HOLD
    assert _rating_from_upside(-0.03) == PortfolioRating.HOLD
    assert _rating_from_upside(-0.15) == PortfolioRating.SELL


def test_valuation_mock_computes_target():
    result = compute_valuation_mock(
        ticker="TEST",
        current_price=100.0,
        forecast_model={"eps_forecast_3y": [1.2, 1.4, 1.6]},
        facts=[],
    )
    assert result.target_price > 0
    assert result.is_mock is True
    assert result.rating in PortfolioRating


def test_rating_upside_mismatch_detected():
    issues = check_rating_upside_consistency(PortfolioRating.BUY.value, 0.05)
    assert "rating_upside_mismatch" in issues

    issues_ok = check_rating_upside_consistency(PortfolioRating.BUY.value, 0.20)
    assert issues_ok == []
