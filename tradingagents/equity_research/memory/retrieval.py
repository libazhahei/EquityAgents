"""Collaborative memory retrieval across research ledgers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from tradingagents.equity_research.memory.embedding_retrieval import (
    hybrid_evidence_candidates,
    semantic_similarity,
)
from tradingagents.equity_research.memory.filters import MemoryFilters, apply_memory_filters
from tradingagents.equity_research.memory.similarity import cosine_similarity, text_similarity, _text_similarity


def memory_score(
    *,
    semantic_similarity: float = 0.5,
    evidence_reliability: float = 0.5,
    thesis_node_score: float = 0.5,
    recency_score: float = 0.5,
    financial_materiality: float = 0.5,
    redundancy_penalty: float = 0.0,
) -> float:
    """Weighted memory retrieval score (feedback §5.4)."""
    return (
        0.30 * semantic_similarity
        + 0.25 * evidence_reliability
        + 0.20 * thesis_node_score
        + 0.15 * recency_score
        + 0.10 * financial_materiality
        - 0.10 * redundancy_penalty
    )


def _recency_score(date_str: str) -> float:
    if not date_str:
        return 0.4
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        days = (datetime.utcnow() - dt.replace(tzinfo=None)).days
        return max(0.1, 1.0 - days / 365.0)
    except (ValueError, TypeError):
        return 0.4


def _similarity_fn(deps: Any | None, query: str, text: str, *, ticker: str, fragment_id: str = ""):
    if deps is not None:
        return semantic_similarity(deps, query, text, ticker=ticker, fragment_id=fragment_id)
    return _text_similarity(query, text)


def build_memory_context(
    state: dict[str, Any],
    parent_nodes: list[str],
    plan: dict[str, Any] | None = None,
    max_items: int = 20,
    filters: MemoryFilters | dict[str, Any] | None = None,
    deps: Any = None,
) -> dict[str, Any]:
    """Retrieve relevant memory from ledgers for current thesis exploration."""
    plan = plan or {}
    filters = filters or {}
    query = " ".join(plan.get("priority_questions", [])[:2])
    if not query:
        graph = state.get("research_graph", {})
        nodes = graph.get("nodes", {})
        for pid in parent_nodes:
            node = nodes.get(pid, {})
            query = node.get("thesis", "") or node.get("research_question", "")
            if query:
                break
    if not query:
        query = state.get("active_objective", state.get("ticker", ""))

    graph = state.get("research_graph", {})
    nodes = graph.get("nodes", {})
    parent_context = [nodes[pid] for pid in parent_nodes if pid in nodes]
    ticker = state.get("ticker", "")

    er = getattr(deps, "config", {}).get("equity_research", {}) if deps is not None else {}
    top_k = int(er.get("memory_semantic_top_k", 30))
    hybrid_scores = hybrid_evidence_candidates(deps, state, query, top_k=top_k)

    evidence_entries = apply_memory_filters(
        state.get("evidence_ledger", []),
        filters,
        ledger_kind="evidence",
    )
    scored_evidence: list[tuple[float, dict]] = []
    seen_texts: set[str] = set()
    for entry in evidence_entries:
        text = entry.get("quote", "")
        eid = entry.get("evidence_id", "")
        redundancy = 1.0 if text[:80] in seen_texts else 0.0
        seen_texts.add(text[:80])
        sem = hybrid_scores.get(eid)
        if sem is None:
            sem = _similarity_fn(
                deps, query, text, ticker=ticker, fragment_id=entry.get("fragment_id", eid)
            )
        score = memory_score(
            semantic_similarity=sem,
            evidence_reliability=float(entry.get("reliability_score", 0.5)),
            thesis_node_score=0.5,
            recency_score=_recency_score(entry.get("date", "") or entry.get("created_at", "")),
            financial_materiality=0.6 if entry.get("metric") else 0.3,
            redundancy_penalty=redundancy,
        )
        scored_evidence.append((score, entry))

    claim_entries = apply_memory_filters(
        state.get("claim_ledger", []),
        filters,
        ledger_kind="claim",
    )
    scored_claims: list[tuple[float, dict]] = []
    for entry in claim_entries:
        text = entry.get("claim", "")
        score = memory_score(
            semantic_similarity=_similarity_fn(deps, query, text, ticker=ticker),
            evidence_reliability=float(entry.get("confidence", 0.5)),
            thesis_node_score=0.7 if entry.get("is_core_thesis") else 0.4,
            recency_score=_recency_score(entry.get("created_at", "")),
            financial_materiality=0.5,
        )
        scored_claims.append((score, entry))

    assumption_entries = apply_memory_filters(
        state.get("assumption_ledger", []),
        filters,
        ledger_kind="assumption",
    )
    scored_assumptions: list[tuple[float, dict]] = []
    for entry in assumption_entries:
        text = f"{entry.get('metric', '')} {entry.get('our_assumption', '')}"
        score = memory_score(
            semantic_similarity=_similarity_fn(deps, query, text, ticker=ticker),
            evidence_reliability=0.5,
            thesis_node_score=0.6 if str(entry.get("sensitivity", "")).lower() == "high" else 0.4,
            recency_score=_recency_score(entry.get("created_at", "")),
            financial_materiality=0.5,
        )
        scored_assumptions.append((score, entry))

    consensus_entries = apply_memory_filters(
        state.get("consensus_ledger", []),
        filters,
        ledger_kind="consensus",
    )
    scored_consensus: list[tuple[float, dict]] = []
    for entry in consensus_entries:
        text = f"{entry.get('metric', '')} {entry.get('consensus_value', '')}"
        score = memory_score(
            semantic_similarity=_similarity_fn(deps, query, text, ticker=ticker),
            evidence_reliability=0.6,
            thesis_node_score=0.5,
            recency_score=_recency_score(entry.get("as_of_date", "") or entry.get("created_at", "")),
            financial_materiality=0.5,
        )
        scored_consensus.append((score, entry))

    scored_evidence.sort(key=lambda x: x[0], reverse=True)
    scored_claims.sort(key=lambda x: x[0], reverse=True)
    scored_assumptions.sort(key=lambda x: x[0], reverse=True)
    scored_consensus.sort(key=lambda x: x[0], reverse=True)

    ledger_types = filters.get("ledger_types") if filters else None
    result = {
        "query": query,
        "parent_nodes": parent_context,
        "failure_patterns": [
            n.get("failure_reason")
            for n in nodes.values()
            if n.get("status") == "rejected" and n.get("failure_reason")
        ][:3],
        "cross_branch_discoveries": state.get("cross_branch_discoveries", [])[:5],
    }
    if not ledger_types or "evidence" in ledger_types:
        result["evidence"] = [e for _, e in scored_evidence[:max_items // 2]]
    else:
        result["evidence"] = []
    if not ledger_types or "claim" in ledger_types:
        result["claims"] = [c for _, c in scored_claims[:max_items // 2]]
    else:
        result["claims"] = []
    if not ledger_types or "assumption" in ledger_types:
        result["assumptions"] = [a for _, a in scored_assumptions[:5]]
    else:
        result["assumptions"] = []
    if not ledger_types or "consensus" in ledger_types:
        result["consensus"] = [c for _, c in scored_consensus[:3]]
    else:
        result["consensus"] = []
    return result


__all__ = [
    "build_memory_context",
    "memory_score",
    "text_similarity",
    "cosine_similarity",
    "_text_similarity",
]
