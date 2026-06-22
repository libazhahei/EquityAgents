"""Risk / counter-thesis agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class RiskAgent(BaseDomainAgent):
    skill_names = ["risk_counterthesis"]
