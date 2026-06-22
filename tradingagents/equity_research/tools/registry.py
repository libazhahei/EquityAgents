"""Tool registry for equity research skills."""

from __future__ import annotations

from typing import Any, Callable

from tradingagents.equity_research.tools import calculators, data_retrieval, evidence_memory


class ToolRegistry:
    """Registry of deterministic equity research tools."""

    def __init__(self, deps: Any | None = None):
        self.deps = deps
        self._tools: dict[str, Callable[..., Any]] = {
            "get_financial_statements": data_retrieval.get_financial_statements,
            "get_consensus_estimates": data_retrieval.get_consensus_estimates,
            "get_current_price": data_retrieval.get_current_price,
            "search_web": data_retrieval.search_web,
            "search_company_filings": data_retrieval.search_company_filings,
            "get_news": data_retrieval.get_news,
            "calculate_cagr": calculators.calculate_cagr,
            "calculate_total_return": calculators.calculate_total_return,
            "calculate_trading_multiple_valuation": calculators.calculate_trading_multiple_valuation,
            "calculate_sensitivity_table": calculators.calculate_sensitivity_table,
            "store_evidence": evidence_memory.store_evidence,
            "store_claim": evidence_memory.store_claim,
            "store_assumption": evidence_memory.store_assumption,
            "link_evidence_to_claim": evidence_memory.link_evidence_to_claim,
            "retrieve_claims_by_section": evidence_memory.retrieve_claims_by_section,
            "retrieve_contradictory_evidence": evidence_memory.retrieve_contradictory_evidence,
        }

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> Callable[..., Any]:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered")
        return self._tools[name]

    def for_skill(self, allowed_tools: list[str]) -> dict[str, Callable[..., Any]]:
        return {name: self._tools[name] for name in allowed_tools if name in self._tools}

    def call(self, name: str, *args, **kwargs) -> Any:
        return self.get(name)(*args, **kwargs)
