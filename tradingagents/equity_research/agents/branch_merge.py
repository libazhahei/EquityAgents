"""Branch merge — combine best thesis branches into final investment focus."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.prompts.rd_agent import thesis_merge_prompt
from tradingagents.equity_research.state.schemas import Claim, ClaimStatus, ClaimType, claim_to_dict


def create_branch_merge(deps: EquityResearchDeps):
    def branch_merge(state: dict[str, Any]) -> dict[str, Any]:
        graph = state.get("research_graph", {})
        nodes = graph.get("nodes", {})
        best_id = graph.get("best_node_id")

        scored = []
        for node_id, raw in nodes.items():
            if raw.get("status") == "rejected":
                continue
            score = float(raw.get("real_score") or raw.get("virtual_score") or 0)
            scored.append((score, node_id, raw))
        scored.sort(reverse=True)
        best_nodes = [raw for _, _, raw in scored[:4]]

        merge_result = _merge_theses(deps, state, best_nodes)
        thesis_ledger = list(state.get("thesis_ledger", []))
        thesis_ledger.append({
            "thesis_id": str(uuid.uuid4()),
            "statement": merge_result.get("final_core_thesis", ""),
            "variant_view": "; ".join(merge_result.get("supporting_points", [])[:3]),
            "confidence": scored[0][0] if scored else 0.5,
        })

        claims = list(state.get("claims", []))
        if merge_result.get("final_core_thesis"):
            claims.append(claim_to_dict(Claim(
                claim_id=str(uuid.uuid4()),
                hypothesis_id=best_id or "merged",
                section_id="1_investment_summary",
                claim_type=ClaimType.RECOMMENDATION,
                text=merge_result["final_core_thesis"],
                status=ClaimStatus.PARTIALLY_SUPPORTED,
                confidence=scored[0][0] if scored else 0.5,
                is_core_thesis=True,
            )))

        updates = {
            "thesis_ledger": thesis_ledger,
            "claims": claims,
            "cross_branch_discoveries": merge_result.get("supporting_points", []),
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "branch_merge", {
            "merged_branches": len(best_nodes),
            "best_node_id": best_id,
        }))
        return updates

    return branch_merge


def _merge_theses(deps: EquityResearchDeps, state: dict[str, Any], best_nodes: list[dict]) -> dict[str, Any]:
    if not best_nodes:
        return {"final_core_thesis": f"Research thesis for {state.get('ticker')}", "supporting_points": []}
    try:
        prompt = thesis_merge_prompt(state, best_nodes)
        response = deps.deep_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {
        "final_core_thesis": best_nodes[0].get("thesis", ""),
        "supporting_points": [n.get("thesis", "") for n in best_nodes[1:3]],
        "integrated_risks": [],
        "catalysts": [],
    }
