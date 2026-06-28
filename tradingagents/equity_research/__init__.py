"""Deep Equity Research — hypothesis-driven sell-side style research workflow."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tradingagents.equity_research.graph.equity_research_graph import EquityResearchGraph


def __getattr__(name: str):
    if name == "EquityResearchGraph":
        from tradingagents.equity_research.graph.equity_research_graph import EquityResearchGraph
        return EquityResearchGraph
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["EquityResearchGraph"]
