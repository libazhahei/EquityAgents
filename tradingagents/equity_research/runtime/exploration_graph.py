"""Exploration graph — chain-mode research history (R&D-Agent G)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass
class ExplorationNode:
    node_id: str
    parent_id: str | None
    branch_id: str
    query_plan: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    structured_view_snapshot: dict = field(default_factory=dict)
    coverage_score: float = 0.0
    routing_decision: str = ""
    iteration: int = 0
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "parent_id": self.parent_id,
            "branch_id": self.branch_id,
            "query_plan": self.query_plan,
            "evidence": self.evidence,
            "structured_view_snapshot": self.structured_view_snapshot,
            "coverage_score": self.coverage_score,
            "routing_decision": self.routing_decision,
            "iteration": self.iteration,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExplorationNode:
        return cls(
            node_id=data.get("node_id", ""),
            parent_id=data.get("parent_id"),
            branch_id=data.get("branch_id", "main"),
            query_plan=list(data.get("query_plan", [])),
            evidence=list(data.get("evidence", [])),
            structured_view_snapshot=dict(data.get("structured_view_snapshot", {})),
            coverage_score=float(data.get("coverage_score", 0.0)),
            routing_decision=str(data.get("routing_decision", "")),
            iteration=int(data.get("iteration", 0)),
            created_at=str(data.get("created_at", "")),
        )


class ExplorationGraph:
    def __init__(self, nodes: dict[str, ExplorationNode] | None = None) -> None:
        self.nodes: dict[str, ExplorationNode] = nodes or {}
        self._branch_roots: dict[str, str] = {}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> ExplorationGraph:
        if not data:
            return cls()
        nodes = {
            nid: ExplorationNode.from_dict(nd)
            for nid, nd in (data.get("nodes") or {}).items()
        }
        graph = cls(nodes)
        graph._branch_roots = dict(data.get("branch_roots") or {})
        return graph

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "branch_roots": self._branch_roots,
        }

    def add_node(self, node: ExplorationNode) -> None:
        self.nodes[node.node_id] = node
        if node.parent_id is None and node.branch_id not in self._branch_roots:
            self._branch_roots[node.branch_id] = node.node_id

    def new_node(
        self,
        *,
        parent_id: str | None = None,
        branch_id: str = "main",
        **kwargs: Any,
    ) -> ExplorationNode:
        node_id = f"exp_{uuid.uuid4().hex[:8]}"
        node = ExplorationNode(
            node_id=node_id,
            parent_id=parent_id,
            branch_id=branch_id,
            created_at=datetime.now(timezone.utc).isoformat(),
            **kwargs,
        )
        self.add_node(node)
        return node

    def select_parents(self, strategy: str = "greedy") -> list[str]:
        if not self.nodes:
            return []
        if strategy == "greedy":
            best = self.best_node()
            return [best.node_id] if best else []
        return list(self.nodes.keys())[-1:]

    def best_node(self) -> ExplorationNode | None:
        if not self.nodes:
            return None
        return max(self.nodes.values(), key=lambda n: (n.coverage_score, n.iteration))

    def to_chain(self) -> list[ExplorationNode]:
        if not self.nodes:
            return []
        by_parent: dict[str | None, list[ExplorationNode]] = {}
        for node in self.nodes.values():
            by_parent.setdefault(node.parent_id, []).append(node)
        chain: list[ExplorationNode] = []
        current_parent: str | None = None
        while by_parent.get(current_parent):
            children = sorted(by_parent[current_parent], key=lambda n: n.iteration)
            if not children:
                break
            child = children[-1]
            chain.append(child)
            current_parent = child.node_id
        return chain

    def latest_node(self) -> ExplorationNode | None:
        chain = self.to_chain()
        return chain[-1] if chain else None
