"""Consensus and expectation gap discovery agents."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.integrations.perplexity import SearchMode
from tradingagents.equity_research.integrations.info_sources import default_registry
from tradingagents.equity_research.state.schemas import ConsensusView, ExpectationGap


def create_discover_consensus(deps: EquityResearchDeps):
    def discover_consensus(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        query = f"{ticker} analyst consensus estimates price target growth expectations"
        result = deps.perplexity.search(query, mode=SearchMode.EXPLORATORY)
        yf_results = default_registry().fetch_all(ticker, "consensus")
        yf_data = yf_results[0] if yf_results else {}
        doc_ids = []
        for url in result.get("citations", [])[:5]:
            doc = deps.documents.register(
                ticker=ticker,
                source_type="news",
                title=url,
                source_url=url,
            )
            doc_ids.append(doc["doc_id"])
        summary = result.get("answer", "")
        if yf_data.get("data"):
            summary += f"\n\nYahoo Finance data: {json.dumps(yf_data['data'], default=str)}"
        view = ConsensusView(
            summary=summary[:4000],
            analyst_consensus=summary[:1500],
            implied_growth=str(yf_data.get("data", {}).get("revenue_growth", "")),
            source_doc_ids=doc_ids,
        )
        updates = {
            "consensus_view": [view.model_dump()],
            "documents": state.get("documents", []) + [{"doc_id": d} for d in doc_ids],
            "api_calls": state.get("api_calls", 0) + 1,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "discover_consensus"))
        return updates

    return discover_consensus


def create_find_expectation_gaps(deps: EquityResearchDeps):
    def find_expectation_gaps(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        consensus = state.get("consensus_view", [{}])[0].get("summary", "")
        prompt = (
            f"Given market consensus for {ticker}:\n{consensus[:2000]}\n\n"
            f"Instrument context:\n{state.get('instrument_context', '')}\n\n"
            "Identify 2-4 expectation gaps (variant views) that could be alpha sources. "
            "Return JSON array with fields: description, alpha_source, materiality (0-1), "
            "verifiability (0-1), related_metrics."
        )
        response = deps.quick_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        gaps = _parse_gaps(text, ticker)
        updates = {
            "expectation_gaps": [g.model_dump() for g in gaps],
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "find_expectation_gaps", {"count": len(gaps)}))
        return updates

    return find_expectation_gaps


def _parse_gaps(text: str, ticker: str) -> list[ExpectationGap]:
    import re

    gaps = []
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            items = json.loads(match.group())
            for item in items[:4]:
                gaps.append(ExpectationGap(
                    gap_id=str(uuid.uuid4()),
                    description=item.get("description", ""),
                    alpha_source=item.get("alpha_source", ""),
                    materiality=float(item.get("materiality", 0.5)),
                    verifiability=float(item.get("verifiability", 0.5)),
                    related_metrics=item.get("related_metrics", []),
                ))
    except (json.JSONDecodeError, ValueError):
        pass
    if not gaps:
        gaps.append(ExpectationGap(
            gap_id=str(uuid.uuid4()),
            description=f"Market may be underestimating {ticker} revenue growth drivers",
            alpha_source="variant_perception",
            materiality=0.6,
            verifiability=0.5,
            related_metrics=["revenue_growth"],
        ))
    return gaps
