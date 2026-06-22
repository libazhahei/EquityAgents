"""Tests for the 10-section equity report template."""

from tradingagents.equity_research.templates.report_template import (
    MVP1_DISPLAY_ORDER,
    MVP1_REPORT_TEMPLATE,
    MVP1_SECTION_ORDER,
    get_investment_summary_template,
)


def test_template_has_ten_sections():
    assert len(MVP1_REPORT_TEMPLATE) == 10
    assert len(MVP1_SECTION_ORDER) == 10
    assert len(MVP1_DISPLAY_ORDER) == 10


def test_investment_summary_first_in_display_order():
    assert MVP1_DISPLAY_ORDER[0] == "1_investment_summary"


def test_valuation_requires_model_output_not_mock():
    valuation = MVP1_REPORT_TEMPLATE["7_valuation"]
    assert valuation.get("requires_model_output") is True
    assert "is_mock" not in valuation


def test_blocking_conditions_use_underscore_format():
    summary = get_investment_summary_template()
    for condition in summary["blocking_conditions"]:
        assert " " not in condition


def test_section_ids_are_sequential():
    numeric_ids = [int(sid.split("_")[0]) for sid in MVP1_REPORT_TEMPLATE]
    assert sorted(numeric_ids) == list(range(1, 11))
