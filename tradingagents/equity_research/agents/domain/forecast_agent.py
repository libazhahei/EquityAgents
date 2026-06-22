"""Forecast agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class ForecastAgent(BaseDomainAgent):
    skill_names = ["forecast_assumption_builder"]
