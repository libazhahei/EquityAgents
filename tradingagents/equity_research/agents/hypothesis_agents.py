"""Hypothesis generation, evaluation, and budget allocation."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.state.schemas import HypothesisNode, HypothesisScores, HypothesisStatus, hypothesis_to_dict
from tradingagents.equity_research.templates.report_template import MVP1_REPORT_TEMPLATE


def create_generate_hypotheses(deps: EquityResearchDeps):
    def generate_hypotheses(state: dict[str, Any]) -> dict[str, Any]:
        section_id = state.get("active_section_id") or "1_investment_summary"
        ticker = state["ticker"]
        gaps = state.get("expectation_gaps", [])
        template = MVP1_REPORT_TEMPLATE.get(section_id, {})
        prompt = (
            f"Generate 3-5 verifiable investment hypotheses for {ticker} "
            f"section '{template.get('title', section_id)}'.\n"
            f"Expectation gaps: {json.dumps(gaps[:3], default=str)}\n"
            f"Required outputs: {template.get('required_outputs', [])}\n"
            "Return JSON array with: statement, consensus_view, variant_view, "
            "key_value_drivers, required_evidence."
        )
        response = deps.quick_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        nodes = _parse_hypotheses(text, ticker, section_id, deps.config)
        hypothesis_nodes = dict(state.get("hypothesis_nodes", {}))
        active_ids = []
        for node in nodes:
            hypothesis_nodes[node.hypothesis_id] = hypothesis_to_dict(node)
            active_ids.append(node.hypothesis_id)
        updates = {
            "hypothesis_nodes": hypothesis_nodes,
            "active_hypothesis_ids": active_ids,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "generate_hypotheses", {"section_id": section_id}))
        return updates

    return generate_hypotheses


def create_virtual_evaluate(deps: EquityResearchDeps):
    def virtual_evaluate(state: dict[str, Any]) -> dict[str, Any]:
        nodes = dict(state.get("hypothesis_nodes", {}))
        pruned = list(state.get("pruned_hypothesis_ids", []))
        active = []
        max_h = deps.config.get("equity_research", {}).get("max_hypotheses_per_section", 5)
        scored = []
        for hid, raw in nodes.items():
            if raw.get("section_targets") and state.get("active_section_id") not in raw.get("section_targets", []):
                continue
            if raw.get("status") == HypothesisStatus.REJECTED.value:
                pruned.append(hid)
                continue
            scores = _score_hypothesis(raw, deps)
            raw["scores"] = scores
            raw["status"] = HypothesisStatus.ACCEPTED.value if scores["priority"] >= 0.4 else HypothesisStatus.REJECTED.value
            nodes[hid] = raw
            if raw["status"] == HypothesisStatus.ACCEPTED.value:
                scored.append((scores["priority"], hid))
            else:
                pruned.append(hid)
        scored.sort(reverse=True)
        active = [hid for _, hid in scored[:max_h]]
        for hid in active:
            nodes[hid]["status"] = HypothesisStatus.IN_RESEARCH.value
        updates = {
            "hypothesis_nodes": nodes,
            "active_hypothesis_ids": active,
            "pruned_hypothesis_ids": pruned,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "virtual_evaluate"))
        return updates

    return virtual_evaluate


def create_allocate_budget(deps: EquityResearchDeps):
    def allocate_budget(state: dict[str, Any]) -> dict[str, Any]:
        report_id = state.get("report_id", "")
        budget = dict(state.get("research_budget", {}))
        budget["remaining_search_queries"] = deps.redis.budget_get(report_id, "search_queries")
        budget["remaining_extraction_docs"] = deps.redis.budget_get(report_id, "extraction_docs")
        completed = len(state.get("completed_sections", []))
        phase = "early" if completed < 2 else ("mid" if completed < 4 else "late")
        updates = {
            "research_budget": budget,
            "research_phase": phase,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "allocate_budget"))
        return updates

    return allocate_budget


def _parse_hypotheses(text: str, ticker: str, section_id: str, config: dict) -> list[HypothesisNode]:
    nodes = []
    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            items = json.loads(match.group())
            for item in items[:5]:
                nodes.append(HypothesisNode(
                    hypothesis_id=str(uuid.uuid4()),
                    ticker=ticker,
                    section_targets=[section_id],
                    statement=item.get("statement", ""),
                    consensus_view=item.get("consensus_view", ""),
                    variant_view=item.get("variant_view", ""),
                    key_value_drivers=item.get("key_value_drivers", []),
                    required_evidence=item.get("required_evidence", []),
                    max_iterations=config.get("equity_research", {}).get("max_hypothesis_iterations", 3),
                ))
    except (json.JSONDecodeError, ValueError):
        pass
    if not nodes:
        nodes.append(HypothesisNode(
            hypothesis_id=str(uuid.uuid4()),
            ticker=ticker,
            section_targets=[section_id],
            statement=f"{ticker} has underappreciated growth in core segments",
            consensus_view="Market prices in moderate growth",
            variant_view="Segment mix shift could accelerate earnings",
            required_evidence=["segment revenue growth", "margin trends"],
        ))
    return nodes


def _score_hypothesis(raw: dict, deps: EquityResearchDeps) -> dict:
    prompt = (
        f"Score this hypothesis 0-1 on materiality, variant_perception, verifiability, "
        f"evidence_availability. Return JSON only.\n{json.dumps(raw, default=str)[:1500]}"
    )
    try:
        response = deps.quick_llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            data = json.loads(match.group())
            scores = HypothesisScores(
                materiality=float(data.get("materiality", 0.5)),
                variant_perception=float(data.get("variant_perception", 0.5)),
                verifiability=float(data.get("verifiability", 0.5)),
                evidence_availability=float(data.get("evidence_availability", 0.5)),
            )
            priority = (
                scores.materiality * 0.3
                + scores.variant_perception * 0.25
                + scores.verifiability * 0.25
                + scores.evidence_availability * 0.2
            )
            scores.priority = priority
            return scores.model_dump()
    except Exception:
        pass
    return HypothesisScores(priority=0.5).model_dump()
