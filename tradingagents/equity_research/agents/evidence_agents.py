"""Evidence retrieval, fact extraction, and claim verification."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.integrations.perplexity import SearchMode, generate_search_plan
from tradingagents.equity_research.state.schemas import Claim, ClaimStatus, ClaimType, claim_to_dict


def create_retrieve_evidence(deps: EquityResearchDeps):
    def retrieve_evidence(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        report_id = state.get("report_id", "")
        active_ids = state.get("active_hypothesis_ids", [])
        if not active_ids:
            return deps.trace(state, "retrieve_evidence", {"skipped": True})
        hid = active_ids[0]
        hypothesis = state.get("hypothesis_nodes", {}).get(hid, {})
        budget = state.get("research_budget", {})
        remaining = deps.redis.budget_get(report_id, "search_queries")
        if remaining <= 0:
            return deps.trace(state, "retrieve_evidence", {"budget_exhausted": True})

        section_id = state.get("active_section_id", "")
        mode = SearchMode.CONTRADICTION if section_id == "7_risks" else SearchMode.TARGETED
        plans = generate_search_plan(ticker, hypothesis, mode, min(remaining, budget.get("max_search_queries", 3)))

        documents = list(state.get("documents", []))
        fragments = list(state.get("evidence_fragments", []))
        contradiction_fragments = list(state.get("contradiction_fragments", []))

        for plan in plans:
            deps.redis.budget_decr(report_id, "search_queries")
            result = deps.perplexity.search(plan["query"], mode=mode)
            for url in result.get("citations", []):
                doc = deps.documents.register(
                    ticker=ticker,
                    source_type="web",
                    title=plan["query"][:200],
                    source_url=url,
                )
                documents.append(doc)
            for para in _split_paragraphs(result.get("answer", "")):
                if len(para) < 40:
                    continue
                doc_id = documents[-1]["doc_id"] if documents else ""
                emb = deps.embeddings.embed(para)
                frag = deps.evidence.insert(
                    ticker=ticker,
                    doc_id=doc_id,
                    excerpt_text=para,
                    hypothesis_id=hid,
                    fragment_type=mode.value,
                    source_reliability="medium",
                    embedding=emb,
                )
                fragments.append(frag)
                if mode == SearchMode.CONTRADICTION:
                    contradiction_fragments.append(frag)

        # EDGAR supplement
        for filing in deps.edgar.fetch_recent_filings(ticker)[:2]:
            doc = deps.documents.register(
                ticker=ticker,
                source_type=filing.get("form", "10-K"),
                title=f"{ticker} {filing.get('form', '')}",
                source_url=filing.get("url", ""),
                published_date=filing.get("filing_date"),
            )
            documents.append(doc)
            if filing.get("text_excerpt"):
                frag = deps.evidence.insert(
                    ticker=ticker,
                    doc_id=doc["doc_id"],
                    excerpt_text=filing["text_excerpt"][:2000],
                    hypothesis_id=hid,
                    fragment_type="filing",
                    source_reliability="high",
                    embedding=deps.embeddings.embed(filing["text_excerpt"][:2000]),
                )
                fragments.append(frag)

        nodes = dict(state.get("hypothesis_nodes", {}))
        if hid in nodes:
            nodes[hid]["research_iterations"] = nodes[hid].get("research_iterations", 0) + 1
            nodes[hid]["supporting_evidence_ids"] = list({
                *nodes[hid].get("supporting_evidence_ids", []),
                *[f["fragment_id"] for f in fragments[-5:]],
            })

        updates = {
            "documents": documents,
            "evidence_fragments": fragments,
            "contradiction_fragments": contradiction_fragments,
            "hypothesis_nodes": nodes,
            "api_calls": state.get("api_calls", 0) + len(plans),
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "retrieve_evidence", {"queries": len(plans)}))
        return updates

    return retrieve_evidence


def create_extract_facts(deps: EquityResearchDeps):
    def extract_facts(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        report_id = state.get("report_id", "")
        if deps.redis.budget_get(report_id, "extraction_docs") <= 0:
            return deps.trace(state, "extract_facts", {"budget_exhausted": True})

        fragments = state.get("evidence_fragments", [])[-10:]
        facts = list(state.get("structured_facts", []))
        for frag in fragments:
            deps.redis.budget_decr(report_id, "extraction_docs")
            prompt = (
                f"Extract numeric KPIs from this excerpt. Return JSON array with "
                f"metric_name, metric_value, unit, fiscal_period.\n\n{frag.get('excerpt_text', '')[:1500]}"
            )
            response = deps.quick_llm.invoke(prompt)
            text = response.content if hasattr(response, "content") else str(response)
            for item in _parse_facts(text):
                fact = deps.facts.insert(
                    ticker=ticker,
                    metric_name=item.get("metric_name", "unknown"),
                    metric_value=item.get("metric_value"),
                    metric_value_text=str(item.get("metric_value", "")),
                    unit=item.get("unit", ""),
                    fiscal_period=item.get("fiscal_period", ""),
                    source_doc_id=frag.get("doc_id", ""),
                    extraction_confidence=0.75,
                )
                facts.append(fact)

        updates = {
            "structured_facts": facts,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "extract_facts", {"count": len(facts)}))
        return updates

    return extract_facts


def create_verify_claims(deps: EquityResearchDeps):
    def verify_claims(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state["ticker"]
        section_id = state.get("active_section_id", "")
        active_ids = state.get("active_hypothesis_ids", [])
        hid = active_ids[0] if active_ids else ""
        hypothesis = state.get("hypothesis_nodes", {}).get(hid, {})
        fragments = {f["fragment_id"]: f for f in state.get("evidence_fragments", [])}
        facts = state.get("structured_facts", [])
        claims = list(state.get("claims", []))

        proposed = Claim(
            claim_id=str(uuid.uuid4()),
            hypothesis_id=hid,
            section_id=section_id,
            claim_type=_section_claim_type(section_id),
            text=hypothesis.get("statement", f"Research finding for {ticker}"),
            supporting_evidence_ids=[
                fid for fid in hypothesis.get("supporting_evidence_ids", [])
                if fid in fragments
            ],
            supporting_fact_ids=[f["fact_id"] for f in facts if f.get("source_doc_id")],
        )
        proposed = _verify_claim(proposed, fragments, facts)
        claims.append(claim_to_dict(proposed))

        nodes = dict(state.get("hypothesis_nodes", {}))
        if hid in nodes and proposed.status == ClaimStatus.VERIFIED:
            nodes[hid]["status"] = "verified"
            verified = list(state.get("verified_hypothesis_ids", []))
            if hid not in verified:
                verified.append(hid)
        else:
            verified = state.get("verified_hypothesis_ids", [])

        updates = {
            "claims": claims,
            "hypothesis_nodes": nodes,
            "verified_hypothesis_ids": verified,
            "last_updated": datetime.utcnow().isoformat(),
        }
        updates.update(deps.trace({**state, **updates}, "verify_claims", {"status": proposed.status.value}))
        return updates

    return verify_claims


def create_evaluate_stop_condition(deps: EquityResearchDeps):
    def evaluate_stop_condition(state: dict[str, Any]) -> dict[str, Any]:
        active_ids = state.get("active_hypothesis_ids", [])
        report_id = state.get("report_id", "")
        remaining = deps.redis.budget_get(report_id, "search_queries")

        if not active_ids or remaining <= 0:
            route = "write_section"
        else:
            hid = active_ids[0]
            node = state.get("hypothesis_nodes", {}).get(hid, {})
            budget = state.get("research_budget", {})
            max_iter = budget.get("max_hypothesis_iterations", 3)
            iterations = node.get("research_iterations", 0)
            verified_claims = [
                c for c in state.get("claims", [])
                if c.get("hypothesis_id") == hid and c.get("status") == ClaimStatus.VERIFIED.value
            ]
            if verified_claims or iterations >= max_iter:
                route = "write_section"
            else:
                route = "retrieve_evidence"
        updates = {"_hypothesis_route": route, "last_updated": datetime.utcnow().isoformat()}
        updates.update(deps.trace({**state, **updates}, "evaluate_stop_condition", {"route": route}))
        return updates

    return evaluate_stop_condition


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]


def _parse_facts(text: str) -> list[dict]:
    import json

    try:
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except (json.JSONDecodeError, ValueError):
        pass
    return []


def _section_claim_type(section_id: str) -> ClaimType:
    mapping = {
        "2_company_overview": ClaimType.DESCRIPTIVE,
        "3_industry_and_competition": ClaimType.INDUSTRY,
        "5_earnings_forecast": ClaimType.FORECAST,
        "6_valuation": ClaimType.VALUATION,
        "7_risks": ClaimType.RISK,
        "1_investment_focus": ClaimType.RECOMMENDATION,
    }
    return mapping.get(section_id, ClaimType.DESCRIPTIVE)


def _verify_claim(claim: Claim, fragments: dict, facts: list) -> Claim:
    has_evidence = any(fid in fragments for fid in claim.supporting_evidence_ids)
    has_fact = len(claim.supporting_fact_ids) > 0
    has_doc = any(fragments.get(fid, {}).get("doc_id") for fid in claim.supporting_evidence_ids)

    if claim.claim_type == ClaimType.RECOMMENDATION and not (has_evidence or has_fact):
        claim.status = ClaimStatus.UNSUPPORTED
    elif has_doc and (has_evidence or has_fact):
        claim.status = ClaimStatus.VERIFIED
        claim.confidence = 0.8 if has_fact else 0.65
    elif has_evidence:
        claim.status = ClaimStatus.PARTIALLY_SUPPORTED
        claim.confidence = 0.5
    else:
        claim.status = ClaimStatus.UNSUPPORTED
    return claim
