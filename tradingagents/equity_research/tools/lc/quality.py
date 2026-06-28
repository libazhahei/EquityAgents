"""LangChain quality verification tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import quality_tools


@tool
def citation_checker(urls: Annotated[list[str], "Citation URLs to verify"]) -> dict[str, Any]:
    """Check whether citation URLs are accessible."""
    return quality_tools.citation_checker(urls)


@tool
def claim_evidence_checker(
    claims: Annotated[list[dict], "Claims with supporting_evidence_ids"],
    evidence: Annotated[list[dict], "Evidence items with evidence_id"],
) -> dict[str, Any]:
    """Check whether claims have supporting evidence."""
    return quality_tools.claim_evidence_checker(claims, evidence)


@tool
def coverage_evaluator(
    artifact: Annotated[dict[str, Any], "Report or artifact to evaluate"],
    criteria: Annotated[list[str], "Coverage criteria keywords"],
) -> dict[str, Any]:
    """Evaluate how well an artifact covers required criteria."""
    return quality_tools.coverage_evaluator(artifact, criteria)


@tool
def conflict_detector(
    evidence: Annotated[list[dict] | dict, "Evidence items to compare for conflicts"],
) -> dict[str, Any]:
    """Detect conflicting evidence items."""
    return quality_tools.conflict_detector(evidence)
