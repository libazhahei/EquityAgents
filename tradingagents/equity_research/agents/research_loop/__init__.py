"""Research loop — section research subgraph runtime."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.research_loop.subgraph import create_run_section_research_subgraph


def create_research_loop(deps: EquityResearchDeps):
    """Run one section research subgraph iteration (replaces legacy 9-step runtime)."""
    run = create_run_section_research_subgraph(deps)

    def research_loop(state: dict[str, Any]) -> dict[str, Any]:
        return run(state)

    return research_loop


__all__ = ["create_research_loop", "create_run_section_research_subgraph"]
