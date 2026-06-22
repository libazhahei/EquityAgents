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
        "required_outputs": [
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
        "required_outputs": [
            "business_description",
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
        "required_outputs": [
            "revenue_model_explanation",
            "key_operating_metrics",
            "pricing_model",
            "customer_and_channel_analysis",
            "unit_economics",
            "margin_driver_analysis",
        ],
        "required_evidence_min": 3,
    },
    "4_industry_and_competition": {
        "title": "Industry Analysis & Competitive Landscape",
        "required_outputs": [
            "tam_estimate",
            "industry_growth_rate",
            "value_chain_analysis",
            "market_share_analysis",
            "competitor_comparison_table",
            "competitive_position_assessment",
            "regulatory_or_policy_factors",
        ],
        "required_evidence_min": 4,
    },
    "5_historical_financials": {
        "title": "Historical Financial Analysis",
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
        "required_outputs": [
            "segment_revenue_forecast_3y",
            "gross_margin_forecast",
            "opex_forecast",
            "ebitda_forecast_3y",
            "net_income_forecast_3y",
            "eps_forecast_3y",
            "free_cash_flow_forecast_3y",
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
        "required_outputs": [
            "valuation_method_rationale",
            "peer_comparison_table",
            "historical_multiple_analysis",
            "target_multiple_or_dcf_assumptions",
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
        "required_outputs": [
            "bull_case_assumptions",
            "base_case_assumptions",
            "bear_case_assumptions",
            "target_price_range",
            "valuation_sensitivity_table",
        ],
        "required_evidence_min": 2,
    },
    "9_risks": {
        "title": "Risk Factors & Counter-thesis",
        "required_outputs": [
            "company_specific_risks",
            "industry_risks",
            "macro_risks",
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
