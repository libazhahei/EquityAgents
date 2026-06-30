"""Collaborative memory retrieval across research ledgers."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any


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


def _text_similarity(query: str, text: str) -> float:
    """Asymmetric query→text token overlap for memory retrieval scoring."""
    if not query or not text:
        return 0.0
    q_tokens = set(query.lower().split())
    t_tokens = set(text.lower().split())
    if not q_tokens:
        return 0.0
    return len(q_tokens & t_tokens) / len(q_tokens)


def text_similarity(a: str, b: str) -> float:
    """Symmetric Jaccard token overlap for deduplication (no embedding required)."""
    if not a or not b:
        return 0.0
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    union = a_tokens | b_tokens
    if not union:
        return 0.0
    return len(a_tokens & b_tokens) / len(union)


def _recency_score(date_str: str) -> float:
    if not date_str:
        return 0.4
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        days = (datetime.utcnow() - dt.replace(tzinfo=None)).days
        return max(0.1, 1.0 - days / 365.0)
    except (ValueError, TypeError):
        return 0.4


def build_memory_context(
    state: dict[str, Any],
    parent_nodes: list[str],
    plan: dict[str, Any] | None = None,
    max_items: int = 20,
) -> dict[str, Any]:
    """Retrieve relevant memory from ledgers for current thesis exploration."""
    plan = plan or {}
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

    scored_evidence: list[tuple[float, dict]] = []
    seen_texts: set[str] = set()
    for entry in state.get("evidence_ledger", []):
        text = entry.get("quote", "")
        redundancy = 1.0 if text[:80] in seen_texts else 0.0
        seen_texts.add(text[:80])
        score = memory_score(
            semantic_similarity=_text_similarity(query, text),
            evidence_reliability=float(entry.get("reliability_score", 0.5)),
            thesis_node_score=0.5,
            recency_score=_recency_score(entry.get("date", "")),
            financial_materiality=0.6 if entry.get("metric") else 0.3,
            redundancy_penalty=redundancy,
        )
        scored_evidence.append((score, entry))

    scored_claims: list[tuple[float, dict]] = []
    for entry in state.get("claim_ledger", []):
        text = entry.get("claim", "")
        score = memory_score(
            semantic_similarity=_text_similarity(query, text),
            evidence_reliability=float(entry.get("confidence", 0.5)),
            thesis_node_score=0.7 if entry.get("is_core_thesis") else 0.4,
            recency_score=0.5,
            financial_materiality=0.5,
        )
        scored_claims.append((score, entry))

    scored_evidence.sort(key=lambda x: x[0], reverse=True)
    scored_claims.sort(key=lambda x: x[0], reverse=True)

    return {
        "query": query,
        "parent_nodes": parent_context,
        "evidence": [e for _, e in scored_evidence[:max_items // 2]],
        "claims": [c for _, c in scored_claims[:max_items // 2]],
        "assumptions": state.get("assumption_ledger", [])[:5],
        "consensus": state.get("consensus_ledger", [])[:3],
        "cross_branch_discoveries": state.get("cross_branch_discoveries", [])[:5],
        "failure_patterns": [
            n.get("failure_reason")
            for n in nodes.values()
            if n.get("status") == "rejected" and n.get("failure_reason")
        ][:3],
    }


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (norm_a * norm_b)
