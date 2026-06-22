"""Equity R&D research loop runtime — inner 9-step thesis graph exploration."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.evidence_agents import (
    create_evaluate_stop_condition,
    create_extract_facts,
    create_retrieve_evidence,
    create_verify_claims,
)
from tradingagents.equity_research.agents.hypothesis_agents import (
    create_allocate_budget,
    create_generate_hypotheses,
    create_virtual_evaluate,
)
from tradingagents.equity_research.evaluation.aggregators import aggregate_thesis_score
from tradingagents.equity_research.memory.retrieval import build_memory_context
from tradingagents.equity_research.prompts.rd_agent import (
    dynamic_planning_prompt,
    key_research_problems_prompt,
    quick_diligence_prompt,
    scientific_hypothesis_prompt,
)
from tradingagents.equity_research.skills.base import SkillInput
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.state.ledgers import sync_ledgers_from_legacy, write_to_ledger
from tradingagents.equity_research.state.research_graph import (
    select_parent_thesis_nodes,
    sync_graph_to_hypothesis_nodes,
    update_research_graph,
)
from tradingagents.equity_research.tools.registry import ToolRegistry


class ResearchLoopRuntime:
    """Single-iteration R&D loop: plan → parents → memory → problems → hypotheses →
    virtual IC → quick diligence → full development → evaluate → update graph."""

    def __init__(self, deps: EquityResearchDeps):
        self.deps = deps
        self.tool_registry = ToolRegistry(deps)
        self.skill_registry = SkillRegistry()
        self._generate_hypotheses = create_generate_hypotheses(deps)
        self._virtual_evaluate = create_virtual_evaluate(deps)
        self._allocate_budget = create_allocate_budget(deps)
        self._retrieve_evidence = create_retrieve_evidence(deps)
        self._extract_facts = create_extract_facts(deps)
        self._verify_claims = create_verify_claims(deps)
        self._evaluate_stop = create_evaluate_stop_condition(deps)

    def run(self, state: dict[str, Any]) -> dict[str, Any]:
        working = dict(state)

        # ① Dynamic planning
        strategy = self._dynamic_plan(working)
        working["research_strategy"] = strategy
        working["research_phase"] = strategy.get("stage", working.get("research_phase", "early"))

        graph = working.get("research_graph", {"nodes": {}, "edges": [], "best_node_id": None, "branches": {}})

        # ② Select parent nodes
        parents = select_parent_thesis_nodes(graph, strategy)
        working["active_hypothesis_ids"] = parents

        # ③ Memory context
        memory_context = build_memory_context(working, parents, strategy)

        # ④ Identify key research problems
        problems = self._identify_problems(working, memory_context)

        # ⑤ Generate hypotheses (scientific reasoning)
        hypotheses = self._generate_scientific_hypotheses(working, problems, memory_context)
        if not hypotheses:
            gen_updates = self._generate_hypotheses(working)
            working.update(gen_updates)
            hypotheses = self._hypotheses_from_state(working)

        # ⑥ Virtual IC evaluation — select best hypothesis
        selected = self._virtual_select(hypotheses, working)
        if not selected:
            selected = hypotheses[0] if hypotheses else self._default_hypothesis(working)

        # ⑦ Quick diligence
        quick = self._quick_diligence(selected, working)
        if quick.get("recommended_action") == "reject":
            graph = update_research_graph(
                graph,
                parents=parents,
                thesis=selected.get("hypothesis", selected.get("statement", "")),
                branch_id=selected.get("category", "unknown"),
                virtual_score=selected.get("overall_score", 0) / 10.0 if selected.get("overall_score") else 0.3,
                real_score=quick.get("confidence", 0.2),
                status="rejected",
                failure_reason=quick.get("reason", "quick_diligence_reject"),
            )
            return self._finalize_iteration(state, working, graph, strategy, selected, quick, rejected=True)

        # ⑧ Full development
        dev_updates = self._full_development(working, selected, strategy)
        working.update(dev_updates)

        # ⑨ Evaluate + update graph
        artifacts = {
            "evidence_ids": [e.get("evidence_id") or e.get("fragment_id") for e in working.get("evidence_fragments", [])[-10:]],
            "claim_ids": [c.get("claim_id") for c in working.get("claims", [])[-5:]],
            "valuation_model": working.get("valuation_model"),
            "forecast_model": working.get("forecast_model"),
            "counter_evidence": quick.get("counter_evidence", []),
        }
        evaluation = aggregate_thesis_score(working, artifacts, selected)
        real_score = evaluation.aggregate_score

        graph = update_research_graph(
            graph,
            parents=parents,
            thesis=selected.get("hypothesis", selected.get("statement", "")),
            research_question=problems[0].get("problem", "") if problems else "",
            branch_id=selected.get("category", selected.get("branch_id", "")),
            artifacts=artifacts,
            evidence_ids=artifacts["evidence_ids"],
            claim_ids=artifacts["claim_ids"],
            virtual_score=selected.get("overall_score", 0) / 10.0 if selected.get("overall_score") else None,
            real_score=real_score,
            status="evaluated" if evaluation.passed else "developed",
        )

        return self._finalize_iteration(state, working, graph, strategy, selected, quick, evaluation=evaluation)

    def _dynamic_plan(self, state: dict[str, Any]) -> dict[str, Any]:
        iterations = int(state.get("research_iterations", 0))
        max_iter = int(state.get("max_research_iterations", 5))
        if iterations < max_iter * 0.3:
            stage = "orientation"
        elif iterations < max_iter * 0.6:
            stage = "thesis_discovery"
        elif iterations < max_iter * 0.85:
            stage = "diligence_modeling"
        else:
            stage = "convergence"

        try:
            prompt = dynamic_planning_prompt(state)
            response = self.deps.quick_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                data.setdefault("stage", stage)
                return data
        except Exception:
            pass

        return {
            "stage": stage,
            "exploration_vs_exploitation": "explore" if stage in ("orientation", "thesis_discovery") else "exploit",
            "priority_questions": [q.get("question", "") for q in state.get("research_plan", {}).get("core_questions", [])[:3]],
            "skills_to_run": ["variant_view_discovery", "business_model_analysis"],
            "budget_allocation": {"evidence_search": 40, "financial_modeling": 20, "valuation": 10},
            "avoid_actions": ["premature_rating"] if stage != "convergence" else [],
            "reason": f"rule-based stage={stage}",
        }

    def _identify_problems(self, state: dict[str, Any], memory_context: dict[str, Any]) -> list[dict]:
        gaps = state.get("expectation_gaps", [])
        if gaps:
            return [
                {
                    "problem": g.get("description", ""),
                    "category": g.get("category", "consensus_gap"),
                    "priority": g.get("priority", "high"),
                }
                for g in gaps[:3]
            ]
        try:
            prompt = key_research_problems_prompt(state, memory_context)
            response = self.deps.quick_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return data.get("key_research_problems", [])
        except Exception:
            pass
        return [{"problem": f"Key variant view for {state.get('ticker')}", "category": "consensus_gap", "priority": "high"}]

    def _generate_scientific_hypotheses(
        self,
        state: dict[str, Any],
        problems: list[dict],
        memory_context: dict[str, Any],
    ) -> list[dict]:
        try:
            prompt = scientific_hypothesis_prompt(state, problems, memory_context)
            response = self.deps.deep_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return data.get("hypotheses", [])
        except Exception:
            pass
        return []

    def _hypotheses_from_state(self, state: dict[str, Any]) -> list[dict]:
        nodes = state.get("hypothesis_nodes", {})
        active = state.get("active_hypothesis_ids", list(nodes.keys())[:3])
        result = []
        for hid in active:
            raw = nodes.get(hid, {})
            result.append({
                "hypothesis": raw.get("statement", ""),
                "category": "variant_view",
                "statement": raw.get("statement", ""),
                "overall_score": (raw.get("scores", {}).get("priority", 0.5) or 0.5) * 10,
                "hypothesis_id": hid,
            })
        return result

    def _virtual_select(self, hypotheses: list[dict], state: dict[str, Any]) -> dict | None:
        if not hypotheses:
            return None
        scored = []
        for h in hypotheses:
            score = float(h.get("overall_score", 5))
            if h.get("recommended_next_action") == "reject":
                score *= 0.3
            elif h.get("recommended_next_action") == "park":
                score *= 0.6
            scored.append((score, h))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    def _quick_diligence(self, hypothesis: dict, state: dict[str, Any]) -> dict[str, Any]:
        try:
            prompt = quick_diligence_prompt(hypothesis)
            response = self.deps.quick_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception:
            pass
        score = float(hypothesis.get("overall_score", 5)) / 10.0
        action = "full_diligence" if score >= 0.5 else "park"
        return {
            "confidence": score,
            "recommended_action": action,
            "reason": "rule-based quick diligence",
            "counter_evidence": [],
        }

    def _full_development(
        self,
        state: dict[str, Any],
        hypothesis: dict,
        strategy: dict[str, Any],
    ) -> dict[str, Any]:
        working = dict(state)
        hid = hypothesis.get("hypothesis_id") or str(uuid.uuid4())
        nodes = dict(working.get("hypothesis_nodes", {}))
        nodes[hid] = {
            "hypothesis_id": hid,
            "statement": hypothesis.get("hypothesis", hypothesis.get("statement", "")),
            "variant_view": hypothesis.get("mechanism", ""),
            "status": "in_research",
            "supporting_evidence_ids": [],
        }
        working["hypothesis_nodes"] = nodes
        working["active_hypothesis_ids"] = [hid]
        working["active_section_id"] = "1_investment_summary"

        working.update(self._allocate_budget(working))
        working.update(self._virtual_evaluate(working))
        working.update(self._retrieve_evidence(working))
        working.update(self._extract_facts(working))
        working.update(self._verify_claims(working))

        # Run skills from planning
        for skill_name in strategy.get("skills_to_run", [])[:2]:
            try:
                skill = self.skill_registry.get(skill_name)
                tools = self.tool_registry.for_skill(skill.manifest.allowed_tools)
                output = skill.run(
                    SkillInput(
                        mandate=working.get("mandate", {}),
                        state_snapshot=working,
                        objective=hypothesis.get("hypothesis", ""),
                    ),
                    tools,
                )
                working["claims"] = working.get("claims", []) + output.claims
                if output.artifacts.get("valuation_model"):
                    working["valuation_model"] = output.artifacts["valuation_model"]
                if output.artifacts.get("historical_financials"):
                    working["historical_financials"] = output.artifacts["historical_financials"]
            except KeyError:
                continue

        return {
            k: working[k]
            for k in (
                "hypothesis_nodes", "active_hypothesis_ids", "verified_hypothesis_ids",
                "claims", "evidence_fragments", "contradiction_fragments",
                "structured_facts", "documents", "research_budget", "api_calls",
                "valuation_model", "historical_financials",
            )
            if k in working
        }

    def _default_hypothesis(self, state: dict[str, Any]) -> dict:
        ticker = state.get("ticker", "")
        return {
            "hypothesis": f"{ticker} has underappreciated variant view versus consensus",
            "category": "consensus_gap",
            "overall_score": 5.0,
            "recommended_next_action": "develop",
        }

    def _finalize_iteration(
        self,
        state: dict[str, Any],
        working: dict[str, Any],
        graph: dict[str, Any],
        strategy: dict[str, Any],
        selected: dict,
        quick: dict,
        *,
        rejected: bool = False,
        evaluation: Any = None,
    ) -> dict[str, Any]:
        iterations = int(state.get("research_iterations", 0)) + 1
        max_iterations = int(state.get("max_research_iterations", 5))
        graph_nodes = graph.get("nodes", {})
        best_id = graph.get("best_node_id")
        best_score = 0.0
        if best_id and best_id in graph_nodes:
            best_score = float(graph_nodes[best_id].get("real_score") or 0)

        er_cfg = self.deps.config.get("equity_research", {})
        score_threshold = float(er_cfg.get("thesis_score_threshold", 0.55))
        stage = strategy.get("stage", "")

        if rejected:
            research_status = "continue"
        elif best_score >= score_threshold and stage == "convergence":
            research_status = "sufficient"
        elif iterations >= max_iterations:
            research_status = "sufficient"
        elif best_score >= score_threshold and len(graph_nodes) >= 3:
            research_status = "sufficient"
        else:
            research_status = "continue"

        merged = {**state, **working}
        merged["research_graph"] = graph
        merged["hypothesis_nodes"] = sync_graph_to_hypothesis_nodes(graph)
        merged["research_iterations"] = iterations
        merged["research_status"] = research_status
        merged["research_strategy"] = strategy
        merged["active_objective"] = selected.get("hypothesis", selected.get("statement", ""))
        merged["last_updated"] = datetime.utcnow().isoformat()

        if evaluation and evaluation.blocking_issues:
            for issue in evaluation.blocking_issues:
                merged.update(write_to_ledger(merged, "issue", {
                    "issue_id": f"eval_{issue}_{iterations}",
                    "gate": "research_loop",
                    "message": issue,
                    "severity": "warning",
                }))

        ledger_sync = sync_ledgers_from_legacy(merged)
        merged.update(ledger_sync)

        trace_payload = {
            "iteration": iterations,
            "stage": stage,
            "selected_thesis": selected.get("hypothesis", "")[:100],
            "quick_action": quick.get("recommended_action"),
            "best_score": best_score,
            "status": research_status,
            "rejected": rejected,
        }
        if evaluation:
            trace_payload["aggregate_score"] = evaluation.aggregate_score

        trace = self.deps.trace(merged, "research_loop", trace_payload)
        merged.update(trace)
        return merged


def create_research_loop(deps: EquityResearchDeps):
    runtime = ResearchLoopRuntime(deps)

    def research_loop(state: dict[str, Any]) -> dict[str, Any]:
        return runtime.run(state)

    return research_loop
