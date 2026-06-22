"""Industry analyst agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class IndustryAnalystAgent(BaseDomainAgent):
    skill_names = ["industry_analysis"]
