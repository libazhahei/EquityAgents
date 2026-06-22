"""Domain analyst agents — logical roles dispatched by Lead Analyst."""

from tradingagents.equity_research.agents.domain.consensus_agent import ConsensusAnalystAgent
from tradingagents.equity_research.agents.domain.evidence_agent import EvidenceAnalystAgent
from tradingagents.equity_research.agents.domain.forecast_agent import ForecastAgent
from tradingagents.equity_research.agents.domain.ic_agent import ICChallengeAgent
from tradingagents.equity_research.agents.domain.industry_agent import IndustryAnalystAgent
from tradingagents.equity_research.agents.domain.business_agent import BusinessAnalystAgent
from tradingagents.equity_research.agents.domain.risk_agent import RiskAgent
from tradingagents.equity_research.agents.domain.valuation_agent import ValuationAgent
from tradingagents.equity_research.agents.domain.writing_agent import WritingAgent

__all__ = [
    "EvidenceAnalystAgent",
    "ConsensusAnalystAgent",
    "BusinessAnalystAgent",
    "IndustryAnalystAgent",
    "ForecastAgent",
    "ValuationAgent",
    "RiskAgent",
    "ICChallengeAgent",
    "WritingAgent",
]
