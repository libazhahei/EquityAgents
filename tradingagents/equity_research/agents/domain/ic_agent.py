"""IC challenge agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class ICChallengeAgent(BaseDomainAgent):
    skill_names = ["standardized_qa"]
