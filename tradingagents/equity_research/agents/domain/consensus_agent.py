"""Consensus analyst agent."""

from tradingagents.equity_research.agents.domain.base import BaseDomainAgent


class ConsensusAnalystAgent(BaseDomainAgent):
    skill_names = ["broker_consensus_mining", "variant_view_discovery"]
