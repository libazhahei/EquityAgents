"""Section template interpretation for section planner."""

from __future__ import annotations

from tradingagents.equity_research.templates.report_template import (
    MVP1_REPORT_TEMPLATE,
    build_grounding_queries,
    get_section_intent_hint,
)


def interpret_section_template(section_id: str) -> dict:
    """Resolve section metadata from MVP1_REPORT_TEMPLATE (no LLM)."""
    template = MVP1_REPORT_TEMPLATE.get(section_id, {})
    if not template:
        raise KeyError(f"Unknown section_id: {section_id}")
    return {
        "section_id": section_id,
        "section_title": str(template.get("title", section_id)),
        "required_outputs": list(template.get("required_outputs", [])),
        "section_intent_hint": get_section_intent_hint(section_id),
        "grounding_query_templates": list(template.get("grounding_queries", [])),
    }


__all__ = ["interpret_section_template", "build_grounding_queries", "get_section_intent_hint"]
