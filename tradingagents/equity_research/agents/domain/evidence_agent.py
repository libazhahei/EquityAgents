"""Evidence analyst agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class EvidenceAnalystAgent(BaseDomainAgent):
    skill_names = ["collaborative_memory"]
