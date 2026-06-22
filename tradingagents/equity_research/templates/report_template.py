"""MVP1 report template — six sections from design.md §15.1."""

from __future__ import annotations

MVP1_SECTION_ORDER = [
    "2_company_overview",
    "3_industry_and_competition",
    "5_earnings_forecast",
    "6_valuation",
    "7_risks",
    "1_investment_focus",
]

MVP1_REPORT_TEMPLATE: dict[str, dict] = {
    "1_investment_focus": {
        "title": "投资聚焦",
        "required_outputs": [
            "investment_rating",
            "target_price",
            "key_financial_summary_table",
            "core_thesis_bullet_points",
            "catalyst_timeline",
        ],
        "required_evidence_min": 3,
        "blocking_conditions": ["rating missing", "target_price missing", "rating_upside_mismatch"],
        "rating_thresholds": {
            "Buy": {"min_upside_pct": 0.15},
            "Overweight": {"min_upside_pct": 0.10},
            "Hold": {"min_upside_pct": -0.10, "max_upside_pct": 0.15},
            "Underperform": {"max_upside_pct": -0.05},
            "Sell": {"max_upside_pct": -0.10},
        },
    },
    "2_company_overview": {
        "title": "公司简介与发展历程",
        "required_outputs": [
            "ownership_structure",
            "management_background",
            "historical_transformation_nodes",
            "business_segment_breakdown",
        ],
        "required_evidence_min": 2,
    },
    "3_industry_and_competition": {
        "title": "行业分析与竞争格局",
        "required_outputs": [
            "tam_estimate",
            "industry_growth_rate",
            "value_chain_analysis",
            "competitor_comparison_table",
            "competitive_position_assessment",
        ],
        "required_evidence_min": 4,
    },
    "5_earnings_forecast": {
        "title": "盈利预测与关键假设",
        "required_outputs": [
            "segment_revenue_forecast_3y",
            "gross_margin_forecast",
            "opex_forecast",
            "eps_forecast_3y",
            "key_assumptions_table",
        ],
        "required_evidence_min": 3,
        "blocking_conditions": ["forecast_assumptions_lack_citations"],
    },
    "6_valuation": {
        "title": "估值分析与投资建议",
        "required_outputs": [
            "valuation_method_rationale",
            "peer_comparison_table",
            "target_price_calculation",
            "rating_explanation",
        ],
        "required_evidence_min": 2,
        "blocking_conditions": [
            "valuation_method_not_justified",
            "target_price_missing",
            "rating_inconsistent_with_upside",
        ],
        "is_mock": True,
    },
    "7_risks": {
        "title": "风险提示",
        "required_outputs": [
            "company_specific_risks",
            "industry_risks",
            "macro_risks",
            "risk_mitigation_discussion",
        ],
        "required_evidence_min": 2,
        "blocking_conditions": ["no_counter_evidence_for_thesis", "risks_are_generic_only"],
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
