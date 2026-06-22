"""Prompt templates for Equity R&D-Agent (feedback §11)."""

from __future__ import annotations

import json
from typing import Any


def research_task_analysis_prompt(state: dict[str, Any]) -> str:
    return (
        "You are a senior equity research analyst.\n"
        "Extract structured research context from the company, documents, and mandate.\n"
        f"Ticker: {state.get('ticker')}\n"
        f"Sector: {state.get('sector')}\nIndustry: {state.get('industry')}\n"
        f"Report type: {state.get('report_type')}\n"
        "Return JSON with: Company, Ticker, Sector, Business Description, Report Type, "
        "Investment Time Horizon, Key Business Segments, Main Revenue Drivers, "
        "Main Margin Drivers, Key Market Debates, Consensus Metrics Available, "
        "Potential Variant View Areas, Required Research Depth, Longer Research Budget Required, Reason."
    )


def dynamic_planning_prompt(state: dict[str, Any]) -> str:
    graph = state.get("research_graph", {})
    strategy = state.get("research_strategy", {})
    return (
        "You are the lead analyst managing an equity research project.\n"
        f"Elapsed iterations: {state.get('research_iterations', 0)}\n"
        f"Max iterations: {state.get('max_research_iterations', 5)}\n"
        f"Research graph nodes: {len(graph.get('nodes', {}))}\n"
        f"Best node score: {graph.get('nodes', {}).get(graph.get('best_node_id', ''), {}).get('real_score', 'N/A')}\n"
        f"Open gaps: {json.dumps(state.get('research_gaps', [])[:3], default=str)}\n"
        f"Prior strategy: {json.dumps(strategy, default=str)[:500]}\n"
        "Return JSON: stage (orientation/thesis_discovery/diligence_modeling/convergence), "
        "exploration_vs_exploitation, priority_questions, skills_to_run, budget_allocation, avoid_actions, reason."
    )


def key_research_problems_prompt(state: dict[str, Any], memory_context: dict[str, Any]) -> str:
    return (
        "You are a senior equity research analyst.\n"
        "Identify the 2-3 most important research problems before making an investment recommendation.\n"
        f"Ticker: {state.get('ticker')}\n"
        f"Expectation gaps: {json.dumps(state.get('expectation_gaps', [])[:4], default=str)}\n"
        f"Memory claims: {json.dumps([c.get('claim', '') for c in memory_context.get('claims', [])[:5]], default=str)}\n"
        "Return JSON with key_research_problems array. Each: problem, category, why_it_matters, "
        "financial_statement_link, required_evidence, priority."
    )


def scientific_hypothesis_prompt(
    state: dict[str, Any],
    problems: list[dict],
    memory_context: dict[str, Any],
) -> str:
    return (
        "You are a research scientist formulating testable investment hypotheses.\n"
        f"Ticker: {state.get('ticker')}\n"
        f"Problems: {json.dumps(problems[:3], default=str)}\n"
        f"Consensus: {json.dumps(state.get('consensus_view', [])[:2], default=str)}\n"
        "For each hypothesis: proposal, mechanism, evidence plan, forecast linkage, five-dimensional scoring (1-10).\n"
        "Classify: Revenue Growth, Margin Expansion, Cost Efficiency, Market Share, Valuation Re-rating, "
        "Capital Allocation, Balance Sheet, Regulatory/Policy, Bear Case.\n"
        "Return JSON with hypotheses array. Each: hypothesis, category, mechanism, "
        "expected_financial_impact, expected_valuation_impact, required_evidence, "
        "potential_counter_evidence, catalysts, scores (alignment, financial_impact, variant_view, "
        "evidence_feasibility, risk_reward), overall_score, recommended_next_action."
    )


def virtual_evaluation_prompt(hypotheses: list[dict]) -> str:
    return (
        "You are an investment committee member reviewing competing equity research thesis branches.\n"
        f"Hypotheses: {json.dumps(hypotheses[:5], default=str)[:3000]}\n"
        "Selection principles: evidence quality primary, variant view preferred, material financial impact, "
        "penalize weak evidence and unclear catalysts.\n"
        "Return JSON: selected_branch_id, explanation, key_supporting_evidence_ids, main_risks, required_follow_up."
    )


def quick_diligence_prompt(hypothesis: dict) -> str:
    return (
        "You are performing a quick diligence check on an investment hypothesis.\n"
        f"Hypothesis: {json.dumps(hypothesis, default=str)[:1500]}\n"
        "Use max 5 evidence items, prefer primary sources, include counter-evidence if available.\n"
        "Return JSON: hypothesis, quick_evidence_summary, counter_evidence, rough_financial_materiality, "
        "confidence (0-1), recommended_action (full_diligence/park/reject), reason."
    )


def research_iteration_analysis_prompt(state: dict[str, Any], current: dict, previous_best: dict | None) -> str:
    return (
        "You are an advanced equity research reviewer analyzing the current research iteration.\n"
        f"Current: {json.dumps(current, default=str)[:1500]}\n"
        f"Previous best: {json.dumps(previous_best or {}, default=str)[:1000]}\n"
        "Return JSON: current_iteration_quality (0-10), improved_vs_previous_best, improvement_reason, "
        "weakened_areas, validated_claims, unsupported_claims, new_reusable_insights, "
        "recommended_next_action (continue/merge/revise/reject)."
    )


def thesis_merge_prompt(state: dict[str, Any], best_nodes: list[dict]) -> str:
    return (
        "You are a senior equity research analyst merging multiple investment thesis branches "
        "into a coherent final investment thesis.\n"
        f"Best branches: {json.dumps(best_nodes[:4], default=str)[:3000]}\n"
        f"Consensus: {json.dumps(state.get('consensus_view', [])[:2], default=str)}\n"
        "Preserve only evidence-supported claims. Resolve contradictions explicitly.\n"
        "Return JSON: final_core_thesis, supporting_points, discarded_claims, "
        "integrated_forecast_assumptions, integrated_risks, catalysts, what_would_change_our_view."
    )
