"""Business analyst agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class BusinessAnalystAgent(BaseDomainAgent):
    skill_names = ["business_model_analysis"]
