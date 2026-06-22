"""Research exploration graph for Equity R&D-Agent thesis branches."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

ResearchNodeStatus = Literal["proposed", "developed", "evaluated", "merged", "rejected"]

DEFAULT_BRANCH_TEMPLATES = [
    {
        "branch_id": "revenue_upside_branch",
        "thesis": "The market underestimates revenue growth potential.",
        "category": "Revenue Growth",
    },
    {
        "branch_id": "margin_expansion_branch",
        "thesis": "The market underestimates gross margin expansion from mix shift and operating leverage.",
        "category": "Margin Expansion",
    },
    {
        "branch_id": "multiple_rerating_branch",
        "thesis": "The market underestimates valuation re-rating potential.",
        "category": "Valuation Re-rating",
    },
    {
        "branch_id": "bear_case_branch",
        "thesis": "The market underestimates competitive or cyclical downside risk.",
        "category": "Bear Case",
    },
    {
        "branch_id": "fcf_return_branch",
        "thesis": "The market underestimates free cash flow and shareholder return potential.",
        "category": "Capital Return",
    },
]


class ResearchNode(BaseModel):
    node_id: str
    parent_ids: list[str] = Field(default_factory=list)
    branch_id: str = ""
    thesis: str = ""
    research_question: str = ""
    expected_model_impact: str = ""
    category: str = ""
    artifacts: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    assumption_ids: list[str] = Field(default_factory=list)
    virtual_score: float | None = None
    real_score: float | None = None
    status: ResearchNodeStatus = "proposed"
    failure_reason: str | None = None


def empty_research_graph() -> dict[str, Any]:
    return {
        "nodes": {},
        "edges": [],
        "best_node_id": None,
        "branches": {},
    }


def init_research_graph_from_gaps(expectation_gaps: list[dict]) -> dict[str, Any]:
    """Initialize exploration graph with default branches plus gap-driven nodes."""
    graph = empty_research_graph()
    parent_id = "initial_consensus_gap"
    graph["nodes"][parent_id] = ResearchNode(
        node_id=parent_id,
        thesis="Market consensus baseline",
        status="evaluated",
        real_score=0.5,
    ).model_dump()

    for template in DEFAULT_BRANCH_TEMPLATES:
        branch_id = template["branch_id"]
        graph["branches"][branch_id] = {
            "branch_id": branch_id,
            "thesis": template["thesis"],
            "category": template["category"],
            "parents": [parent_id],
        }

    for idx, gap in enumerate(expectation_gaps[:3]):
        node_id = f"gap_branch_{idx}"
        graph["nodes"][node_id] = ResearchNode(
            node_id=node_id,
            parent_ids=[parent_id],
            branch_id=gap.get("gap_id", f"gap_{idx}"),
            thesis=gap.get("description", ""),
            research_question=gap.get("description", ""),
            category="consensus_gap",
            status="proposed",
        ).model_dump()
        graph["edges"].append({"from": parent_id, "to": node_id})

    return graph


def select_parent_thesis_nodes(
    graph: dict[str, Any],
    plan: dict[str, Any] | None = None,
    max_parents: int = 2,
) -> list[str]:
    """Score-based parent selection with diversity across branches."""
    nodes = graph.get("nodes", {})
    if not nodes:
        return []

    scored: list[tuple[float, str]] = []
    for node_id, raw in nodes.items():
        if raw.get("status") == "rejected":
            continue
        score = raw.get("real_score") or raw.get("virtual_score") or 0.3
        if raw.get("status") in ("evaluated", "developed", "merged"):
            score += 0.1
        scored.append((float(score), node_id))

    scored.sort(reverse=True)
    selected: list[str] = []
    seen_branches: set[str] = set()
    for _, node_id in scored:
        branch = nodes[node_id].get("branch_id", node_id)
        if branch in seen_branches and len(selected) >= 1:
            continue
        selected.append(node_id)
        seen_branches.add(branch)
        if len(selected) >= max_parents:
            break

    if not selected and scored:
        selected = [scored[0][1]]
    return selected


def update_research_graph(
    graph: dict[str, Any],
    *,
    parents: list[str],
    thesis: str,
    research_question: str = "",
    branch_id: str = "",
    artifacts: dict[str, Any] | None = None,
    evidence_ids: list[str] | None = None,
    claim_ids: list[str] | None = None,
    assumption_ids: list[str] | None = None,
    virtual_score: float | None = None,
    real_score: float | None = None,
    status: ResearchNodeStatus = "evaluated",
    category: str = "",
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """Add a new node to the research graph and update best_node_id."""
    graph = {
        "nodes": dict(graph.get("nodes", {})),
        "edges": list(graph.get("edges", [])),
        "best_node_id": graph.get("best_node_id"),
        "branches": dict(graph.get("branches", {})),
    }
    node_id = str(uuid.uuid4())
    node = ResearchNode(
        node_id=node_id,
        parent_ids=parents,
        branch_id=branch_id,
        thesis=thesis,
        research_question=research_question or thesis,
        category=category,
        artifacts=artifacts or {},
        evidence_ids=evidence_ids or [],
        claim_ids=claim_ids or [],
        assumption_ids=assumption_ids or [],
        virtual_score=virtual_score,
        real_score=real_score,
        status=status,
        failure_reason=failure_reason,
    )
    graph["nodes"][node_id] = node.model_dump()
    for parent_id in parents:
        graph["edges"].append({"from": parent_id, "to": node_id})

    if branch_id:
        graph["branches"].setdefault(branch_id, {"branch_id": branch_id, "thesis": thesis, "parents": parents})

    best_id = graph.get("best_node_id")
    best_score = 0.0
    if best_id and best_id in graph["nodes"]:
        best_score = float(graph["nodes"][best_id].get("real_score") or 0)
    if real_score is not None and real_score >= best_score and status != "rejected":
        graph["best_node_id"] = node_id

    return graph


def sync_hypothesis_nodes_to_graph(state: dict[str, Any]) -> dict[str, Any]:
    """Migrate legacy hypothesis_nodes into research_graph nodes."""
    graph = state.get("research_graph") or empty_research_graph()
    hypothesis_nodes = state.get("hypothesis_nodes", {})
    for hid, raw in hypothesis_nodes.items():
        if hid in graph.get("nodes", {}):
            continue
        graph["nodes"][hid] = ResearchNode(
            node_id=hid,
            parent_ids=raw.get("parent_ids", []),
            thesis=raw.get("statement", ""),
            research_question=raw.get("variant_view", raw.get("statement", "")),
            virtual_score=raw.get("scores", {}).get("priority"),
            status="developed" if raw.get("status") == "verified" else "proposed",
            evidence_ids=raw.get("supporting_evidence_ids", []),
        ).model_dump()
    return graph


def sync_graph_to_hypothesis_nodes(graph: dict[str, Any]) -> dict[str, dict]:
    """Backward-compat: mirror research_graph nodes to hypothesis_nodes."""
    hypothesis_nodes: dict[str, dict] = {}
    for node_id, raw in graph.get("nodes", {}).items():
        hypothesis_nodes[node_id] = {
            "hypothesis_id": node_id,
            "statement": raw.get("thesis", ""),
            "variant_view": raw.get("research_question", ""),
            "status": raw.get("status", "proposed"),
            "scores": {"priority": raw.get("real_score") or raw.get("virtual_score") or 0.5},
            "supporting_evidence_ids": raw.get("evidence_ids", []),
        }
    return hypothesis_nodes
