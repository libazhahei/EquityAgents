"""Task analysis workflow — basic company context + consensus/assumption subgraphs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from tradingagents.equity_research.agents.assumption import create_run_assumption_subgraph
from tradingagents.equity_research.agents.consensus import create_run_consensus_subgraph
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.integrations.sec_cache import (
    ingest_documents_from_sec_cache,
    prefetch_sec_filings,
)
from tradingagents.equity_research.state.equity_research_state import EquityResearchState


def create_analyze_research_task(deps: EquityResearchDeps):
    """Minimal init spine: company context ingest + consensus + assumption."""
    _consensus_subgraph = create_run_consensus_subgraph(deps)
    _assumption_subgraph = create_run_assumption_subgraph(deps)
    def analyze_research_task(state: EquityResearchState) -> dict[str, Any]:
        working = dict(state)

        ticker = str(working.get("ticker", ""))
        prefetch_sec_filings(deps, ticker)
        working.update(ingest_documents_from_sec_cache(deps, working))

        working.update(_consensus_subgraph(working))
        working.update(_assumption_subgraph(working))
        working["subgraph_outputs"] = {
            "consensus": {
                "report": working.get("consensus_report", ""),
                "coverage_report": working.get("consensus_coverage_report", {}),
                "structured_view": working.get("consensus_view", {}),
            },
            "assumption": {
                "report": working.get("assumption_report", ""),
                "coverage_report": working.get("assumption_coverage_report", {}),
                "structured_view": working.get("assumption_view", {}),
            },
        }
        documents = cast(list[dict[str, Any]], working.get("documents", []))
        api_calls = int(cast(int, working.get("api_calls", 0)))
        working["last_updated"] = datetime.utcnow().isoformat()
        working.update(deps.trace(working, "analyze_research_task", {
            "subgraphs": ["consensus", "assumption"],
            "documents": len(documents),
            "api_calls": api_calls,
        }))
        return working

    return analyze_research_task
