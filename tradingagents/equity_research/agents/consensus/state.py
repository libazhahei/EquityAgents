"""State types for the consensus subgraph."""

from __future__ import annotations

from typing import Any, TypedDict


class ConsensusSubgraphState(TypedDict, total=False):
    ticker: str
    sector: str
    report_type: str
    instrument_context: str
    report_id: str
    documents: list[dict]
    api_calls: int

    messages: list[Any]

    active_skills: list[str]
    active_skill_context: dict[str, Any]
    skill_catalog: list[dict]

    query_queue: list[dict]
    executed_queries: list[str]
    evidence_buffer: list[dict]
    pending_evidence: list[dict]
    search_memory: list[dict]

    consensus_view: dict
    consensus_assumptions: dict
    consensus_report: str
    coverage_report: dict
    coverage_history: list[dict]
    consensus_iterations: int
    max_consensus_iterations: int

    assumption_probe_completed: bool
    assumption_pending_evidence: list[dict]

    human_followup_query: str
    human_followup_history: list[str]
    human_review_payload: dict[str, Any]
    _pending_human_followup: bool

    compliance_flags: list[dict]

    errors: list[str]
    research_traces: list[dict]
    last_updated: str


def empty_consensus_subgraph_state(
    parent: dict[str, Any],
    *,
    max_iterations: int = 5,
) -> ConsensusSubgraphState:
    return {
        "ticker": parent.get("ticker", ""),
        "sector": parent.get("sector", ""),
        "report_type": parent.get("report_type", "initiation"),
        "instrument_context": parent.get("instrument_context", ""),
        "report_id": parent.get("report_id", ""),
        "documents": list(parent.get("documents", [])),
        "api_calls": int(parent.get("api_calls", 0)),
        "messages": [],
        "active_skills": [],
        "active_skill_context": {},
        "skill_catalog": [],
        "query_queue": [],
        "executed_queries": [],
        "evidence_buffer": [],
        "pending_evidence": [],
        "search_memory": list(parent.get("consensus_search_memory", [])),
        "consensus_view": {},
        "consensus_assumptions": {},
        "consensus_report": "",
        "coverage_report": {},
        "coverage_history": [],
        "consensus_iterations": 0,
        "max_consensus_iterations": max_iterations,
        "assumption_probe_completed": False,
        "assumption_pending_evidence": [],
        "human_followup_query": "",
        "human_followup_history": list(parent.get("human_followup_history", [])),
        "human_review_payload": {},
        "compliance_flags": list(parent.get("compliance_flags", [])),
        "errors": list(parent.get("errors", [])),
        "research_traces": list(parent.get("research_traces", [])),
    }
