"""Professional equity research report template — ten sections."""

from __future__ import annotations

# Processing order: research sections first, investment summary second-to-last, appendix last.
MVP1_SECTION_ORDER = [
    "2_company_overview",
    "3_business_model",
    "4_industry_and_competition",
    "5_historical_financials",
    "6_earnings_forecast",
    "7_valuation",
    "8_scenario_and_sensitivity",
    "9_risks",
    "1_investment_summary",
    "10_appendix",
]

# Final report display: executive summary first, then numbered sections.
MVP1_DISPLAY_ORDER = [
    "1_investment_summary",
    "2_company_overview",
    "3_business_model",
    "4_industry_and_competition",
    "5_historical_financials",
    "6_earnings_forecast",
    "7_valuation",
    "8_scenario_and_sensitivity",
    "9_risks",
    "10_appendix",
]

MVP1_REPORT_TEMPLATE: dict[str, dict] = {
    "1_investment_summary": {
        "title": "Executive Summary & Investment Thesis",
        "intent_hint": (
            "Focus on investment rating, target price, expected return, "
            "core thesis, variant view, and a strict catalyst timeline. "
            "CRITICAL: Design this section to be readable in under 60 seconds by a retail investor. "
            "Use clear, jargon-free language to explain *why* the stock will move and *when*. "
            "Include a 'Bottom Line' statement summarizing the asymmetrical risk/reward."
        ),
        "grounding_queries": [
            "{ticker} analyst rating target price consensus latest",
            "{ticker} investment thesis catalyst timeline",
        ],
        "required_outputs": [
            "retail_tldr_bottom_line",
            "investment_rating",
            "target_price",
            "current_price",
            "expected_total_return_pct",
            "market_cap",
            "key_financial_summary_table",
            "core_thesis_bullet_points",
            "variant_view",
            "catalyst_timeline",
        ],
        "required_evidence_min": 3,
        "blocking_conditions": [
            "rating_missing",
            "target_price_missing",
            "current_price_missing",
            "rating_upside_mismatch",
            "no_variant_view",
        ],
        "rating_basis": "12_month_total_return",
        "rating_thresholds": {
            "Buy": {"min_upside_pct": 0.15},
            "Overweight": {"min_upside_pct": 0.10},
            "Hold": {"min_upside_pct": -0.10, "max_upside_pct": 0.15},
            "Underperform": {"max_upside_pct": -0.05},
            "Sell": {"max_upside_pct": -0.10},
        },
    },
    "2_company_overview": {
        "title": "Company Overview",
        "intent_hint": (
            "Focus on business identity, corporate history, ownership, management, "
            "segment mix, geographic mix, and major transformation milestones. "
            "Whenever introducing complex industry-specific terms or technology (e.g., 'CoWoS', 'ASIC'), "
            "provide a brief, plain-English translation or analogy for non-technical readers."
        ),
        "grounding_queries": [
            "{ticker} company overview business segments geographic mix",
            "{ticker} management team ownership structure",
        ],
        "required_outputs": [
            "business_description",
            "jargon_translation_glossary",
            "ownership_structure",
            "management_background",
            "historical_transformation_nodes",
            "business_segment_breakdown",
            "geographic_breakdown",
        ],
        "required_evidence_min": 2,
    },
    "3_business_model": {
        "title": "Business Model & Revenue Drivers",
        "intent_hint": (
            "Focus on how the company makes money, revenue mechanics, pricing model, "
            "customers/channels, unit economics, operating metrics, and margin drivers. "
            "Enhance traditional analysis with alternative data signals where available "
            "(e.g., web traffic trends, consumer transaction panels, app downloads, or job posting data) "
            "to validate current operating momentum."
        ),
        "grounding_queries": [
            "{ticker} revenue model pricing unit economics",
            "{ticker} key operating metrics margin drivers",
            "{ticker} alternative data web traffic hiring trends",
        ],
        "required_outputs": [
            "revenue_model_explanation",
            "key_operating_metrics",
            "pricing_model",
            "customer_and_channel_analysis",
            "unit_economics",
            "margin_driver_analysis",
            "alternative_data_momentum_signals",
        ],
        "required_evidence_min": 3,
    },
    "4_industry_and_competition": {
        "title": "Industry Analysis & Competitive Landscape",
        "intent_hint": (
            "Focus on TAM, industry growth, value chain position, market share, competitor comparison, "
            "competitive moat, substitution risk, and regulation. "
            "Include constraints on TAM growth (e.g., physical limits like data center power availability or supply chain bottlenecks). "
            "Ensure competitor comparisons are dynamic, highlighting market share shifts rather than just static positions."
        ),
        "grounding_queries": [
            "{ticker} market share competitors latest",
            "{ticker} industry growth TAM competition latest",
        ],
        "required_outputs": [
            "tam_estimate_and_physical_constraints",
            "industry_growth_rate",
            "value_chain_analysis",
            "dynamic_market_share_analysis",
            "competitor_comparison_table",
            "competitive_position_assessment",
            "regulatory_or_policy_factors",
        ],
        "required_evidence_min": 4,
    },
    "5_historical_financials": {
        "title": "Historical Financial Analysis",
        "intent_hint": (
            "Focus on revenue growth history, segment performance, gross margin, operating margin, "
            "cash flow, balance sheet quality, and return metrics. "
            "Use clear visual cues or narrative explanations to link historical financial inflections "
            "to real-world events or product cycles, making the numbers tell a story."
        ),
        "grounding_queries": [
            "{ticker} historical revenue gross margin cash flow trend",
        ],
        "required_outputs": [
            "revenue_growth_history",
            "segment_performance_history",
            "gross_margin_trend",
            "operating_margin_trend",
            "cash_flow_analysis",
            "balance_sheet_quality",
            "return_metrics",
        ],
        "required_evidence_min": 3,
    },
    "6_earnings_forecast": {
        "title": "Financial Forecast & Key Assumptions",
        "intent_hint": (
            "Focus on forward financial assumptions, segment revenue forecast, gross margin, opex, "
            "EBITDA, net income, EPS, FCF, and explicit key assumptions. "
            "Incorporate insights from management tone/sentiment during recent earnings calls. "
            "Clearly distinguish between 'Management Guidance', 'Consensus Expectations', and 'Our Proprietary Estimates'."
        ),
        "grounding_queries": [
            "{ticker} guidance analyst consensus revenue EPS forecast",
            "{ticker} earnings call sentiment tone analysis",
        ],
        "required_outputs": [
            "segment_revenue_forecast_3y",
            "gross_margin_forecast",
            "opex_forecast",
            "ebitda_forecast_3y",
            "net_income_forecast_3y",
            "eps_forecast_3y",
            "free_cash_flow_forecast_3y",
            "management_sentiment_analysis",
            "key_assumptions_table",
        ],
        "required_evidence_min": 3,
        "blocking_conditions": [
            "forecast_assumptions_lack_citations",
            "forecast_not_tied_to_business_drivers",
        ],
    },
    "7_valuation": {
        "title": "Valuation Analysis",
        "intent_hint": (
            "Focus on valuation method rationale, peer set, historical multiples, DCF or target multiple "
            "assumptions, target price calculation, implied upside/downside, and rating explanation. "
            "CRITICAL for professional rigor: Include a 'Reverse DCF / Implied Growth' analysis. Calculate what "
            "revenue growth or margin assumptions are currently 'priced in' to the stock, and debate if those "
            "expectations are realistic."
        ),
        "grounding_queries": [
            "{ticker} valuation multiple peer comparison target price consensus",
            "{ticker} implied growth rate reverse DCF",
        ],
        "required_outputs": [
            "valuation_method_rationale",
            "dynamic_peer_comparison_table",
            "historical_multiple_analysis",
            "target_multiple_or_dcf_assumptions",
            "reverse_dcf_market_implied_expectations",
            "target_price_calculation",
            "implied_upside_downside",
            "rating_explanation",
        ],
        "required_evidence_min": 2,
        "requires_model_output": True,
        "blocking_conditions": [
            "valuation_method_not_justified",
            "target_price_missing",
            "rating_inconsistent_with_upside",
            "peer_set_not_justified",
        ],
    },
    "8_scenario_and_sensitivity": {
        "title": "Scenario Analysis & Sensitivity",
        "intent_hint": (
            "Focus on bull/base/bear assumptions, target price range, and sensitivity to the key variables "
            "that drive valuation. "
            "Present this data clearly so a retail investor can easily grasp the asymmetry of the trade "
            "(e.g., 'If X happens, we lose 10%; if Y happens, we gain 50%')."
        ),
        "grounding_queries": [
            "{ticker} bull bear case scenario sensitivity valuation",
        ],
        "required_outputs": [
            "bull_case_assumptions",
            "base_case_assumptions",
            "bear_case_assumptions",
            "target_price_range",
            "risk_reward_asymmetry_summary",
            "valuation_sensitivity_table",
        ],
        "required_evidence_min": 2,
    },
    "9_risks": {
        "title": "Risk Factors, Market Sentiment & Counter-thesis",
        "intent_hint": (
            "Focus on company-specific risks, industry risks, macro risks, thesis-breaking risks, "
            "counter-evidence, and what would change the investment view. "
            "Include a Market Sentiment & Positioning check: analyze retail sentiment, options market positioning "
            "(e.g., Put/Call ratios), or short interest to identify crowded trades or contrarian setups."
        ),
        "grounding_queries": [
            "{ticker} key risks regulatory competition latest",
            "{ticker} short interest options put call ratio sentiment",
        ],
        "required_outputs": [
            "company_specific_risks",
            "industry_risks",
            "macro_risks",
            "market_sentiment_and_positioning",
            "risk_to_thesis_mapping",
            "counter_evidence_for_core_thesis",
            "what_would_change_our_view",
        ],
        "required_evidence_min": 2,
        "blocking_conditions": [
            "no_counter_evidence_for_thesis",
            "risks_are_generic_only",
            "risks_not_mapped_to_thesis",
        ],
    },
    "10_appendix": {
        "title": "Appendix & Source Notes",
        "intent_hint": (
            "Focus on source list, model notes, data quality flags, methodology notes, and disclaimers. "
            "Ensure alternative data sources (if used) are clearly cited with their limitations noted."
        ),
        "grounding_queries": [],
        "required_outputs": [
            "source_list",
            "financial_model_notes",
            "data_quality_flags",
            "methodology_notes",
            "compliance_disclaimer",
        ],
        "required_evidence_min": 1,
    },
}


def get_mvp1_template_list() -> list[dict]:
    return [
        {"section_id": sid, **MVP1_REPORT_TEMPLATE[sid]}
        for sid in MVP1_SECTION_ORDER
    ]


def section_coverage_entry(section_id: str) -> dict:
    template = MVP1_REPORT_TEMPLATE[section_id]
    return {
        "section_id": section_id,
        "required_outputs": list(template["required_outputs"]),
        "completed_outputs": [],
        "coverage_score": 0.0,
    }


def get_investment_summary_template() -> dict:
    return MVP1_REPORT_TEMPLATE["1_investment_summary"]


_DEFAULT_GROUNDING_QUERIES = [
    "{ticker} latest earnings call key debates",
    "{ticker} consensus estimates key assumptions",
    "{ticker} {section_title} latest developments",
]

_MAX_GROUNDING_QUERIES = 5


def get_section_intent_hint(section_id: str) -> str:
    template = MVP1_REPORT_TEMPLATE.get(section_id, {})
    return str(template.get("intent_hint", ""))


def build_grounding_queries(section_id: str, ticker: str) -> list[str]:
    """Build up to 5 grounding search queries for section planner."""
    template = MVP1_REPORT_TEMPLATE.get(section_id, {})
    section_title = str(template.get("title", section_id))
    ctx = {"ticker": ticker, "section_title": section_title, "section_id": section_id}

    queries: list[str] = []
    seen: set[str] = set()

    def _add(template_str: str) -> None:
        if len(queries) >= _MAX_GROUNDING_QUERIES:
            return
        try:
            q = template_str.format(**ctx).strip()
        except (KeyError, ValueError):
            q = template_str.strip()
        if q and q not in seen:
            seen.add(q)
            queries.append(q)

    for tmpl in _DEFAULT_GROUNDING_QUERIES:
        _add(tmpl)
    for tmpl in template.get("grounding_queries", []):
        _add(str(tmpl))

    return queries[:_MAX_GROUNDING_QUERIES]