"""Consensus gap discovery agent (runs after consensus subgraph)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.consensus.context_compact import compact_if_needed
from tradingagents.equity_research.agents.consensus.prompt_format import format_consensus_view
from tradingagents.equity_research.agents.consensus.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.consensus_schemas import (
    CONSENSUS_DIMENSIONS,
    ExpectationGapBatch,
    StructuredConsensusView,
)
from tradingagents.equity_research.state.schemas import ExpectationGap


def _max_retries(deps: EquityResearchDeps) -> int:
    return int(deps.config.get("equity_research", {}).get("structured_output_max_retries", 3))


def _consensus_text_for_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    view_raw = state.get("consensus_view") or {}
    if isinstance(view_raw, list):
        return (view_raw[0] if view_raw else {}).get("summary", "")
    if not view_raw:
        return "No structured consensus data available."
    try:
        view = StructuredConsensusView.model_validate(view_raw)
        text = format_consensus_view(view)
    except Exception:
        text = str(view_raw)[:6000]
    return compact_if_needed(deps, text, purpose="consensus view for gap analysis")


def create_gap_finder(deps: EquityResearchDeps):
    def gap_finder(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        consensus_text = _consensus_text_for_prompt(deps, state)
        dimensions = "\n".join(f"- {dim}" for dim in CONSENSUS_DIMENSIONS)

        prompt = (
            f"Given structured market consensus for {ticker}:\n{consensus_text}\n\n"
            f"Instrument context:\n{state.get('instrument_context', '')}\n\n"
            f"Analyze each dimension:\n{dimensions}\n\n"
            "Identify 2-4 expectation gaps (variant views) that could be alpha sources.\n"
            "Each gap must include:\n"
            "- description\n"
            "- alpha_source\n"
            "- materiality (0-1)\n"
            "- verifiability (0-1)\n"
            "- related_metrics (list of metric names)\n"
            "- source_dimension (one of the dimensions above)\n"
            "- consensus_assumption\n"
            "- variant_view"
        )

        def _fallback() -> ExpectationGapBatch:
            return ExpectationGapBatch(gaps=[])

        try:
            batch = invoke_structured_with_retry(
                deps.deep_llm,
                ExpectationGapBatch,
                prompt,
                agent_name="gap_finder",
                max_attempts=_max_retries(deps),
                fallback=_fallback,
            )
            gaps = _gaps_from_batch(batch, ticker)
        except StructuredOutputUnsupported:
            gaps = _fallback_gaps(ticker)
        except Exception:
            gaps = _fallback_gaps(ticker)

        if not gaps:
            gaps = _fallback_gaps(ticker)

        updates = {
            "expectation_gaps": [g.model_dump() for g in gaps],
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "gap_finder", {"count": len(gaps)}))
        return updates

    return gap_finder


# Backward-compatible alias
create_find_expectation_gaps = create_gap_finder


def _gaps_from_batch(batch: ExpectationGapBatch, ticker: str) -> list[ExpectationGap]:
    gaps: list[ExpectationGap] = []
    for item in batch.gaps:
        gaps.append(ExpectationGap(
            gap_id=str(uuid.uuid4()),
            description=item.description,
            alpha_source=item.alpha_source,
            materiality=item.materiality,
            verifiability=item.verifiability,
            related_metrics=list(item.related_metrics),
            source_dimension=item.source_dimension,
            consensus_assumption=item.consensus_assumption,
            variant_view=item.variant_view,
        ))
    return gaps


def _fallback_gaps(ticker: str) -> list[ExpectationGap]:
    return [ExpectationGap(
        gap_id=str(uuid.uuid4()),
        description=f"Market may be underestimating {ticker} revenue growth drivers",
        alpha_source="variant_perception",
        materiality=0.6,
        verifiability=0.5,
        related_metrics=["revenue_growth"],
        source_dimension="quantitative_estimates",
        consensus_assumption="Consensus embeds moderate growth",
        variant_view="Growth drivers may accelerate faster than priced",
    )]
