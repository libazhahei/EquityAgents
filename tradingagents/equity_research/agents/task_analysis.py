"""Task analysis workflow — merges mandate, ingest, consensus, assumptions, gaps, init graph."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.assumption import create_run_assumption_subgraph
from tradingagents.equity_research.agents.consensus import create_run_consensus_subgraph
from tradingagents.equity_research.agents.consensus_agents import create_gap_finder
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.init_agents import create_load_report_template
from tradingagents.equity_research.agents.workflow_agents import (
    create_build_source_index,
    create_define_research_mandate,
    create_extract_broker_views,
    create_generate_research_plan,
)
from tradingagents.equity_research.integrations.sec_cache import (
    ingest_documents_from_sec_cache,
    prefetch_sec_filings,
)
from tradingagents.equity_research.prompts.rd_agent import research_task_analysis_prompt
from tradingagents.equity_research.state.equity_research_state import EquityResearchState
from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy
from tradingagents.equity_research.state.research_graph import init_research_graph_from_gaps


def create_analyze_research_task(deps: EquityResearchDeps):
    """Combined init spine: template, mandate, SEC ingest, consensus, assumption, gaps, plan, graph."""

    _mandate = create_define_research_mandate(deps)
    _template = create_load_report_template(deps)
    _source_index = create_build_source_index(deps)
    _broker = create_extract_broker_views(deps)
    _consensus_subgraph = create_run_consensus_subgraph(deps)
    _assumption_subgraph = create_run_assumption_subgraph(deps)
    _gap_finder = create_gap_finder(deps)
    _plan = create_generate_research_plan(deps)

    def analyze_research_task(state: EquityResearchState) -> dict[str, Any]:
        working = dict(state)
        working.update(_template(working))
        working.update(_mandate(working))

        ticker = str(working.get("ticker", ""))
        prefetch_sec_filings(deps, ticker)
        working.update(ingest_documents_from_sec_cache(deps, working))

        working.update(_consensus_subgraph(working))
        working.update(_assumption_subgraph(working))

        working.update(_source_index(working))

        if deps.fmp.available:
            transcripts = deps.fmp.fetch_earnings_call_transcripts(ticker, limit=2)
            documents = list(working.get("documents", []))
            for tr in transcripts:
                doc = deps.documents.register(
                    ticker=ticker,
                    source_type="earnings_call",
                    title=f"{ticker} Earnings Call {tr.get('date', '')}",
                    published_date=tr.get("date"),
                )
                documents.append(doc)
                if tr.get("content"):
                    frag = deps.evidence.insert(
                        ticker=ticker,
                        doc_id=doc["doc_id"],
                        excerpt_text=tr["content"][:3000],
                        fragment_type="earnings_call",
                        source_reliability="high",
                        embedding=deps.embeddings.embed(tr["content"][:2000]),
                    )
                    working.setdefault("evidence_fragments", []).append(frag)
            working["documents"] = documents

        working.update(_broker(working))
        working.update(_gap_finder(working))
        working.update(_plan(working))

        task_analysis = _run_task_analysis(deps, working)
        working["task_analysis"] = task_analysis

        graph = init_research_graph_from_gaps(working.get("expectation_gaps", []))
        working["research_graph"] = graph
        working["research_status"] = "continue"
        working["research_iterations"] = 0

        ledger_sync = sync_ledgers_from_legacy(working)
        working.update(ledger_sync)
        working["last_updated"] = datetime.utcnow().isoformat()
        working.update(deps.trace(working, "analyze_research_task", {
            "gaps": len(working.get("expectation_gaps", [])),
            "graph_branches": len(graph.get("branches", {})),
            "research_directions": len(working.get("research_directions", [])),
        }))
        return working

    return analyze_research_task


def _run_task_analysis(deps: EquityResearchDeps, state: dict[str, Any]) -> dict[str, Any]:
    try:
        prompt = research_task_analysis_prompt(state)
        response = deps.deep_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {
        "Ticker": state.get("ticker"),
        "Sector": state.get("sector"),
        "Report Type": state.get("report_type"),
        "Required Research Depth": "Medium",
    }
