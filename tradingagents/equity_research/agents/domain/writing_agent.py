"""Report writing agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class WritingAgent(BaseDomainAgent):
    skill_names = ["section_writing"]
