"""Aggregated thesis evaluation for Equity R&D-Agent."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


THESIS_SCORE_WEIGHTS = {
    "evidence_strength": 0.20,
    "consensus_gap_strength": 0.20,
    "financial_materiality": 0.20,
    "valuation_impact": 0.15,
    "catalyst_clarity": 0.10,
    "risk_adjusted_quality": 0.10,
    "novelty": 0.05,
}


@dataclass
class EvaluationResult:
    dimension_scores: dict[str, float] = field(default_factory=dict)
    aggregate_score: float = 0.0
    blocking_issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    passed: bool = False


class EvidenceEvaluator:
    def evaluate(self, state: dict[str, Any], artifacts: dict[str, Any]) -> float:
        evidence_ids = artifacts.get("evidence_ids", [])
        ledger = {e["evidence_id"]: e for e in state.get("evidence_ledger", [])}
        if not evidence_ids:
            fragments = state.get("evidence_fragments", [])
            return 0.3 if fragments else 0.1
        scores = []
        for eid in evidence_ids:
            entry = ledger.get(eid, {})
            scores.append(
                0.6 * float(entry.get("reliability_score", 0.5))
                + 0.4 * float(entry.get("freshness_score", 0.5))
            )
        return sum(scores) / len(scores) if scores else 0.3


class ForecastEvaluator:
    def evaluate(self, state: dict[str, Any], artifacts: dict[str, Any]) -> float:
        assumptions = state.get("model_assumptions", []) or artifacts.get("assumptions", [])
        forecast = state.get("forecast_model") or artifacts.get("forecast_model")
        score = 0.2
        if assumptions:
            score += 0.4
        if forecast:
            score += 0.4
        return min(1.0, score)


class ValuationEvaluator:
    def evaluate(self, state: dict[str, Any], artifacts: dict[str, Any]) -> float:
        vm = artifacts.get("valuation_model") or state.get("valuation_model")
        if not vm:
            return 0.2
        if vm.get("target_price") and vm.get("rating"):
            return 0.8
        return 0.5


class BearCaseEvaluator:
    def evaluate(self, state: dict[str, Any], artifacts: dict[str, Any]) -> float:
        counter = artifacts.get("counter_evidence", []) or state.get("contradiction_fragments", [])
        risk_map = state.get("risk_map", [])
        if counter and risk_map:
            return 0.8
        if counter or risk_map:
            return 0.55
        return 0.3


class ComplianceEvaluator:
    def evaluate(self, state: dict[str, Any], artifacts: dict[str, Any]) -> float:
        unsupported = [
            c for c in state.get("claims", [])
            if c.get("status") == "unsupported" and c.get("claim_type") == "recommendation_claim"
        ]
        if unsupported:
            return 0.2
        return 0.9


def aggregate_thesis_score(
    state: dict[str, Any],
    artifacts: dict[str, Any],
    hypothesis: dict | None = None,
) -> EvaluationResult:
    """Compute weighted thesis score from multiple evaluators."""
    evidence_eval = EvidenceEvaluator()
    forecast_eval = ForecastEvaluator()
    valuation_eval = ValuationEvaluator()
    bear_eval = BearCaseEvaluator()
    compliance_eval = ComplianceEvaluator()

    evidence_strength = evidence_eval.evaluate(state, artifacts)
    consensus_gap = 0.6 if state.get("expectation_gaps") else 0.3
    if hypothesis and hypothesis.get("scores", {}).get("variant_view"):
        consensus_gap = float(hypothesis["scores"]["variant_view"]) / 10.0
    financial_materiality = 0.5
    if hypothesis and hypothesis.get("scores", {}).get("financial_impact"):
        financial_materiality = float(hypothesis["scores"]["financial_impact"]) / 10.0
    valuation_impact = valuation_eval.evaluate(state, artifacts)
    catalyst_clarity = 0.5
    if hypothesis and hypothesis.get("catalysts"):
        catalyst_clarity = min(1.0, 0.4 + 0.15 * len(hypothesis["catalysts"]))
    risk_adjusted = bear_eval.evaluate(state, artifacts)
    novelty = 0.5
    if hypothesis and hypothesis.get("overall_score"):
        novelty = min(1.0, float(hypothesis["overall_score"]) / 10.0)

    dimension_scores = {
        "evidence_strength": evidence_strength,
        "consensus_gap_strength": consensus_gap,
        "financial_materiality": financial_materiality,
        "valuation_impact": valuation_impact,
        "catalyst_clarity": catalyst_clarity,
        "risk_adjusted_quality": risk_adjusted,
        "novelty": novelty,
    }
    aggregate = sum(
        THESIS_SCORE_WEIGHTS[k] * v for k, v in dimension_scores.items()
    )

    blocking = []
    warnings = []
    if evidence_strength < 0.3:
        blocking.append("insufficient_evidence")
    if compliance_eval.evaluate(state, artifacts) < 0.5:
        blocking.append("compliance_concern")
    if risk_adjusted < 0.3:
        warnings.append("bear_case_underexplored")

    return EvaluationResult(
        dimension_scores=dimension_scores,
        aggregate_score=round(aggregate, 3),
        blocking_issues=blocking,
        warnings=warnings,
        passed=len(blocking) == 0 and aggregate >= 0.45,
    )


def aggregate_ic_scores(state: dict[str, Any]) -> EvaluationResult:
    """IC-level aggregated evaluation across full state."""
    artifacts = {
        "evidence_ids": [e.get("evidence_id") for e in state.get("evidence_ledger", [])],
        "valuation_model": state.get("valuation_model"),
        "forecast_model": state.get("forecast_model"),
    }
    result = aggregate_thesis_score(state, artifacts)
    if not state.get("rating"):
        result.blocking_issues.append("rating_missing")
    if not state.get("target_price"):
        result.blocking_issues.append("target_price_missing")
    if not state.get("expectation_gaps"):
        result.blocking_issues.append("no_variant_view")
    graph = state.get("research_graph", {})
    if not graph.get("best_node_id"):
        result.warnings.append("no_best_thesis_node")
    result.passed = len(result.blocking_issues) == 0
    return result
