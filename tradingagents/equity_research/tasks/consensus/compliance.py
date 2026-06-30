"""Data compliance helpers for consensus research."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_MNPI_PATTERNS = re.compile(
    r"\b(insider\s+tip|non[- ]public|mnpi|material\s+non[- ]public|"
    r"expert\s+network\s+call|channel\s+check)\b",
    re.IGNORECASE,
)

_BLOCKED_HOST_FRAGMENTS = (
    "whatsapp",
    "telegram",
    "discord.gg",
)


def get_consensus_compliance_config(config: dict[str, Any] | None) -> dict[str, Any]:
    er = (config or {}).get("equity_research", {})
    defaults = {
        "require_public_citations": True,
        "block_on_mnpi_risk": False,
        "allowed_source_types": ["news", "filing", "earnings_call", "consensus_data"],
    }
    overrides = er.get("consensus_compliance") or {}
    return {**defaults, **overrides}


COMPLIANCE_QUERY_SUFFIX = (
    "Use only publicly available sources: SEC filings, earnings calls, "
    "broker research summaries, news, and free public consensus aggregators. "
    "Do not use MNPI, insider tips, or unauthorized expert network content."
)

PUBLIC_DATA_SOURCE_NOTE = (
    "Data access: searches use public web sources only. "
    "You do NOT have access to paid professional terminals or databases "
    "(FactSet, Bloomberg Terminal, Refinitiv/Eikon, S&P Capital IQ, etc.). "
    "Write queries for publicly available evidence only: SEC filings, earnings "
    "call transcripts, broker research summaries, financial news, and free "
    "consensus aggregator pages."
)


def append_compliance_suffix(query: str) -> str:
    base = str(query).strip()
    if not base:
        return base
    if "publicly available" in base.lower():
        return base[:500]
    combined = f"{base} {COMPLIANCE_QUERY_SUFFIX}"
    return combined[:500]


def _is_public_url(url: str) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    host = (urlparse(url).netloc or "").lower()
    return not any(fragment in host for fragment in _BLOCKED_HOST_FRAGMENTS)


def filter_compliant_citations(
    citations: list[str],
    *,
    config: dict[str, Any] | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    compliance = get_consensus_compliance_config(config)
    require_public = bool(compliance.get("require_public_citations", True))
    kept: list[str] = []
    flags: list[dict[str, Any]] = []

    for citation in citations:
        text = str(citation).strip()
        if not text:
            flags.append({
                "type": "missing_citation",
                "message": "Empty citation removed",
                "source": text,
            })
            continue
        if _MNPI_PATTERNS.search(text):
            flags.append({
                "type": "mnpi_risk",
                "message": "Citation text suggests non-public information",
                "source": text[:200],
            })
            if compliance.get("block_on_mnpi_risk"):
                continue
        if require_public and not _is_public_url(text):
            flags.append({
                "type": "non_public_source",
                "message": "Citation is not a public HTTP(S) URL",
                "source": text[:200],
            })
            continue
        kept.append(text)

    return kept, flags


def check_assumption_evidence_compliance(
    evidence: list[dict[str, Any]],
    assumptions: dict[str, Any],
    *,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    for item in evidence:
        citations = item.get("citations") or []
        _, item_flags = filter_compliant_citations(citations, config=config)
        flags.extend(item_flags)
        if not citations:
            flags.append({
                "type": "missing_citation",
                "message": "Assumption probe evidence has no citations",
                "query": item.get("query_used", "")[:200],
            })

    sources = assumptions.get("sources") or []
    if not sources and any(assumptions.get(k) for k in (
        "business_model", "market_sentiment", "valuation_rationale",
    )):
        flags.append({
            "type": "missing_citation",
            "message": "Consensus assumptions lack source URLs",
        })

    return flags
