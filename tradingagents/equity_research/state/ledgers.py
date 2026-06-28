"""Ledger helpers and hybrid research state models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from tradingagents.equity_research.state.consensus_schemas import StructuredConsensusView


class EvidenceLedgerEntry(BaseModel):
    evidence_id: str
    source_id: str = ""
    source_type: str = ""
    date: str = ""
    quote: str = ""
    metric: str = ""
    value: str = ""
    period: str = ""
    reliability_score: float = 0.0
    freshness_score: float = 0.0
    doc_id: str = ""


class ClaimLedgerEntry(BaseModel):
    claim_id: str
    section_id: str = ""
    claim: str = ""
    claim_type: str = "descriptive_claim"
    direction: str = ""
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    status: str = "proposed"
    is_core_thesis: bool = False
    hypothesis_id: str = ""


class AssumptionLedgerEntry(BaseModel):
    assumption_id: str
    metric: str = ""
    our_assumption: str = ""
    consensus: str = ""
    difference: str = ""
    rationale: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    sensitivity: str = "medium"
    used_in: list[str] = Field(default_factory=list)


class ThesisLedgerEntry(BaseModel):
    thesis_id: str
    statement: str = ""
    variant_view: str = ""
    supporting_claim_ids: list[str] = Field(default_factory=list)
    risk_ids: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class ConsensusLedgerEntry(BaseModel):
    consensus_id: str
    metric: str = ""
    consensus_value: str = ""
    source: str = ""
    as_of_date: str = ""
    broker_count: int = 0


class BrokerViewLedgerEntry(BaseModel):
    view_id: str
    broker: str = ""
    rating: str = ""
    target_price: str = ""
    summary: str = ""
    citations: list[str] = Field(default_factory=list)
    as_of_date: str = ""


class ForecastLedgerEntry(BaseModel):
    forecast_id: str
    version: int = 1
    eps_forecast: dict | list = Field(default_factory=dict)
    revenue_forecast: dict | list = Field(default_factory=dict)
    assumption_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ValuationLedgerEntry(BaseModel):
    valuation_id: str
    version: int = 1
    method: str = ""
    target_price: float | None = None
    rating: str = ""
    upside_pct: float = 0.0
    assumption_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class IssueLedgerEntry(BaseModel):
    issue_id: str
    gate: str = ""
    severity: str = "blocking"
    message: str = ""
    resolution: str = ""
    status: str = "open"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ResearchMandate(BaseModel):
    ticker: str = ""
    report_type: str = "initiation"
    time_horizon: str = "12m"
    currency: str = "USD"
    target_reader: str = "institutional"
    allowed_sources: list[str] = Field(default_factory=lambda: ["filings", "news", "market_data"])
    allow_broker_reports: bool = True
    require_human_approval: bool = False


class ResearchPlanQuestion(BaseModel):
    id: str
    question: str
    priority: str = "medium"
    linked_sections: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    status: str = "pending"


class ResearchPlan(BaseModel):
    core_questions: list[ResearchPlanQuestion] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


def fragment_to_evidence_entry(fragment: dict[str, Any]) -> dict[str, Any]:
    return EvidenceLedgerEntry(
        evidence_id=fragment.get("fragment_id", fragment.get("evidence_id", "")),
        source_id=fragment.get("source_id", ""),
        source_type=fragment.get("source_type", ""),
        date=fragment.get("date", ""),
        quote=fragment.get("text", fragment.get("quote", "")),
        metric=fragment.get("metric", ""),
        value=str(fragment.get("value", "")),
        doc_id=fragment.get("doc_id", ""),
        reliability_score=float(fragment.get("reliability_score", 0.5)),
        freshness_score=float(fragment.get("freshness_score", 0.5)),
    ).model_dump()


def claim_dict_to_ledger_entry(claim: dict[str, Any]) -> dict[str, Any]:
    return ClaimLedgerEntry(
        claim_id=claim.get("claim_id", ""),
        section_id=claim.get("section_id", ""),
        claim=claim.get("text", claim.get("claim", "")),
        claim_type=claim.get("claim_type", "descriptive_claim"),
        supporting_evidence=claim.get("supporting_evidence_ids", []),
        contradicting_evidence=claim.get("contradicting_evidence_ids", []),
        confidence=float(claim.get("confidence", 0.0)),
        status=claim.get("status", "proposed"),
        is_core_thesis=bool(claim.get("is_core_thesis", False)),
        hypothesis_id=claim.get("hypothesis_id", ""),
    ).model_dump()


def assumption_dict_to_ledger_entry(assumption: dict[str, Any]) -> dict[str, Any]:
    if isinstance(assumption, str):
        assumption = {"metric": assumption, "our_assumption": assumption}
    return AssumptionLedgerEntry(
        assumption_id=assumption.get("assumption_id", assumption.get("id", "")),
        metric=assumption.get("metric", ""),
        our_assumption=str(assumption.get("our_assumption", assumption.get("value", ""))),
        consensus=str(assumption.get("consensus", "")),
        difference=str(assumption.get("difference", "")),
        rationale=assumption.get("rationale", ""),
        evidence_ids=assumption.get("evidence_ids", []),
        sensitivity=assumption.get("sensitivity", "medium"),
        used_in=assumption.get("used_in", []),
    ).model_dump()


def write_to_ledger(state: dict[str, Any], ledger_type: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Primary write path for skills/tools into ledger structures."""
    key = f"{ledger_type}_ledger" if not ledger_type.endswith("_ledger") else ledger_type
    ledger = list(state.get(key, []))
    id_field = {
        "evidence": "evidence_id",
        "claim": "claim_id",
        "assumption": "assumption_id",
        "consensus": "consensus_id",
        "broker_view": "view_id",
        "forecast": "forecast_id",
        "valuation": "valuation_id",
        "issue": "issue_id",
    }.get(ledger_type.replace("_ledger", ""), "id")
    entry_id = entry.get(id_field, "")
    existing_ids = {e.get(id_field) for e in ledger}
    if entry_id and entry_id not in existing_ids:
        ledger.append(entry)
    return {key: ledger}


def sync_ledgers_from_legacy(state: dict[str, Any]) -> dict[str, Any]:
    """Bidirectional sync: legacy fields <-> ledger structures."""
    evidence_ledger = list(state.get("evidence_ledger", []))
    existing_evidence_ids = {e.get("evidence_id") for e in evidence_ledger}
    for fragment in state.get("evidence_fragments", []):
        entry = fragment_to_evidence_entry(fragment)
        if entry["evidence_id"] and entry["evidence_id"] not in existing_evidence_ids:
            evidence_ledger.append(entry)
            existing_evidence_ids.add(entry["evidence_id"])

    claim_ledger = list(state.get("claim_ledger", []))
    existing_claim_ids = {c.get("claim_id") for c in claim_ledger}
    for claim in state.get("claims", []):
        entry = claim_dict_to_ledger_entry(claim)
        if entry["claim_id"] and entry["claim_id"] not in existing_claim_ids:
            claim_ledger.append(entry)
            existing_claim_ids.add(entry["claim_id"])

    assumption_ledger = list(state.get("assumption_ledger", []))
    existing_assumption_ids = {a.get("assumption_id") for a in assumption_ledger}
    for idx, assumption in enumerate(state.get("model_assumptions", [])):
        entry = assumption_dict_to_ledger_entry(assumption)
        if not entry["assumption_id"]:
            entry["assumption_id"] = f"asm_{idx}"
        if entry["assumption_id"] not in existing_assumption_ids:
            assumption_ledger.append(entry)
            existing_assumption_ids.add(entry["assumption_id"])

    consensus_ledger = list(state.get("consensus_ledger", []))
    existing_consensus_ids = {c.get("consensus_id") for c in consensus_ledger}
    raw_consensus = state.get("consensus_view", [])
    consensus_entries: list[dict] = []
    if isinstance(raw_consensus, dict) and raw_consensus:
        try:
            view = StructuredConsensusView.model_validate(raw_consensus)
            consensus_entries = view.to_ledger_entries()
        except Exception:
            consensus_entries = [{
                "consensus_id": "cons_0",
                "metric": "overall",
                "summary": str(raw_consensus.get("summary", ""))[:500],
                "value": str(raw_consensus.get("summary", ""))[:500],
                "source": "perplexity",
            }]
    elif isinstance(raw_consensus, list):
        consensus_entries = list(raw_consensus)
    for idx, view in enumerate(consensus_entries):
        entry = ConsensusLedgerEntry(
            consensus_id=view.get("consensus_id", f"cons_{idx}"),
            metric=view.get("metric", "overall"),
            consensus_value=str(view.get("summary", view.get("value", "")))[:500],
            source=view.get("source", "perplexity"),
        ).model_dump()
        if entry["consensus_id"] not in existing_consensus_ids:
            consensus_ledger.append(entry)

    broker_view_ledger = list(state.get("broker_view_ledger", []))
    existing_view_ids = {v.get("view_id") for v in broker_view_ledger}
    for view in state.get("broker_views", []):
        entry = BrokerViewLedgerEntry(
            view_id=view.get("view_id", ""),
            summary=view.get("summary", "")[:2000],
            citations=view.get("citations", []),
        ).model_dump()
        if entry["view_id"] and entry["view_id"] not in existing_view_ids:
            broker_view_ledger.append(entry)

    valuation_ledger = list(state.get("valuation_ledger", []))
    if state.get("valuation_model") and not valuation_ledger:
        vm = state["valuation_model"]
        valuation_ledger.append(
            ValuationLedgerEntry(
                valuation_id=f"val_{len(valuation_ledger)}",
                method=state.get("valuation_method", "trading_multiple"),
                target_price=vm.get("target_price"),
                rating=vm.get("rating", ""),
            ).model_dump()
        )

    forecast_ledger = list(state.get("forecast_ledger", []))
    if state.get("forecast_model") and not forecast_ledger:
        forecast_ledger.append(
            ForecastLedgerEntry(
                forecast_id="fc_0",
                eps_forecast=state["forecast_model"].get("eps_forecast_3y", {}),
                revenue_forecast=state["forecast_model"].get("revenue_forecast_3y", {}),
            ).model_dump()
        )

    issue_ledger = list(state.get("issue_ledger", []))
    existing_issue_ids = {i.get("issue_id") for i in issue_ledger}
    for finding in state.get("review_findings", []):
        if isinstance(finding, str):
            entry = IssueLedgerEntry(issue_id=f"iss_{len(issue_ledger)}", message=finding, gate="review").model_dump()
            if entry["issue_id"] not in existing_issue_ids:
                issue_ledger.append(entry)
    ic = state.get("ic_review") or {}
    for blocking in ic.get("blocking_issues", []):
        entry = IssueLedgerEntry(
            issue_id=f"ic_{blocking}",
            gate="investment_committee_review",
            message=blocking,
            severity="blocking",
        ).model_dump()
        if entry["issue_id"] not in existing_issue_ids:
            issue_ledger.append(entry)

    # Mirror ledgers back to legacy fields where applicable
    claims = list(state.get("claims", []))
    claim_ids_in_legacy = {c.get("claim_id") for c in claims}
    for entry in claim_ledger:
        if entry.get("claim_id") not in claim_ids_in_legacy:
            claims.append({
                "claim_id": entry["claim_id"],
                "section_id": entry.get("section_id", ""),
                "text": entry.get("claim", ""),
                "claim_type": entry.get("claim_type", "descriptive_claim"),
                "status": entry.get("status", "proposed"),
                "confidence": entry.get("confidence", 0.0),
                "supporting_evidence_ids": entry.get("supporting_evidence", []),
            })

    evidence_fragments = list(state.get("evidence_fragments", []))
    frag_ids = {f.get("fragment_id") for f in evidence_fragments}
    for entry in evidence_ledger:
        eid = entry.get("evidence_id", "")
        if eid and eid not in frag_ids:
            evidence_fragments.append({
                "fragment_id": eid,
                "text": entry.get("quote", ""),
                "doc_id": entry.get("doc_id", ""),
                "reliability_score": entry.get("reliability_score", 0.5),
            })

    return {
        "evidence_ledger": evidence_ledger,
        "claim_ledger": claim_ledger,
        "assumption_ledger": assumption_ledger,
        "consensus_ledger": consensus_ledger,
        "broker_view_ledger": broker_view_ledger,
        "valuation_ledger": valuation_ledger,
        "forecast_ledger": forecast_ledger,
        "issue_ledger": issue_ledger,
        "claims": claims,
        "evidence_fragments": evidence_fragments,
    }
