"""Evaluation package for equity research."""

from tradingagents.equity_research.evaluation.aggregators import (
    EvaluationResult,
    aggregate_ic_scores,
    aggregate_thesis_score,
)

__all__ = ["EvaluationResult", "aggregate_thesis_score", "aggregate_ic_scores"]
