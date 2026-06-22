"""Unit tests for claim verification logic."""

from tradingagents.equity_research.agents.evidence_agents import _section_claim_type, _verify_claim
from tradingagents.equity_research.state.schemas import Claim, ClaimStatus, ClaimType


def test_verify_claim_requires_doc_for_verified():
    claim = Claim(
        claim_id="c1",
        hypothesis_id="h1",
        section_id="2_company_overview",
        claim_type=ClaimType.DESCRIPTIVE,
        text="Company grew revenue 20%",
        supporting_evidence_ids=["frag1"],
    )
    fragments = {
        "frag1": {"fragment_id": "frag1", "doc_id": "doc1", "excerpt_text": "revenue up"},
    }
    result = _verify_claim(claim, fragments, [])
    assert result.status == ClaimStatus.VERIFIED

    claim2 = Claim(
        claim_id="c1b",
        hypothesis_id="h1",
        section_id="2_company_overview",
        claim_type=ClaimType.DESCRIPTIVE,
        text="Unverified claim",
        supporting_evidence_ids=["frag_missing"],
    )
    result_partial = _verify_claim(claim2, fragments, [])
    assert result_partial.status == ClaimStatus.UNSUPPORTED


def test_unsupported_recommendation_without_evidence():
    claim = Claim(
        claim_id="c2",
        hypothesis_id="h2",
        section_id="1_investment_focus",
        claim_type=ClaimType.RECOMMENDATION,
        text="Buy the stock",
    )
    result = _verify_claim(claim, {}, [])
    assert result.status == ClaimStatus.UNSUPPORTED


def test_section_claim_type_mapping():
    assert _section_claim_type("7_risks") == ClaimType.RISK
    assert _section_claim_type("6_valuation") == ClaimType.VALUATION
