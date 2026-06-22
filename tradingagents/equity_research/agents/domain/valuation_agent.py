"""Valuation agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class ValuationAgent(BaseDomainAgent):
    skill_names = ["valuation"]
