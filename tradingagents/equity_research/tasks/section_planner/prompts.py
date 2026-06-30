"""Prompt builders for section question tree planner."""

from __future__ import annotations

import json
from typing import Any

from tradingagents.equity_research.tasks.section_planner.schemas import SectionPlannerRequest


def pack_background(reports: dict[str, str], max_chars: int = 20000) -> str:
    parts = []
    for name, text in reports.items():
        if text:
            parts.append(f"## {name}\n{text}")
    packed = "\n\n".join(parts)
    return packed[:max_chars]


def build_background_extractor_prompt(req: SectionPlannerRequest, background: str) -> str:
    return f"""You are an equity research analyst extracting section-relevant context from background reports.

Ticker: {req.ticker}
Section ID: {req.section_id}
Section Title: {req.section_title}
Section Intent: {req.section_intent_hint or "Not specified"}

BACKGROUND REPORTS:
{background or "No background provided."}

Extract ONLY what is relevant to this section. Do not write the report section.
Return structured JSON with:
- market_implied_assumptions
- controversies
- model_drivers
- evidence_for
- evidence_against
- falsification_tests
- evidence_gaps
- next_data_to_watch

Mark uncertain facts as needing verification. Do not invent verified facts.
"""


def build_question_tree_prompt(
    req: SectionPlannerRequest,
    background: str,
    extracted_background: dict[str, Any],
    grounding_notes: str,
) -> str:
    schema_hint = {
        "planning_thesis": "string",
        "root_question": "string",
        "nodes": [
            {
                "id": "q0",
                "parent_id": None,
                "level": 0,
                "question": "string",
                "rationale": "string",
                "priority": 1,
                "required_evidence": ["string"],
                "suggested_sources": ["string"],
                "expected_output": "string",
                "downstream_agent": "string_or_null",
                "stop_condition_hint": "string_or_null",
            }
        ],
        "coverage_map": {output: ["q_id"] for output in req.required_outputs},
        "execution_order": ["q0"],
        "data_quality_flags": ["string"],
        "planner_notes": "string_or_null",
    }

    return f"""You are an equity research section planner.

Your job is NOT to write the report section.
Your job is to create an executable research question tree for ONE section of a professional equity research report.

INPUTS:
Ticker: {req.ticker}
Section ID: {req.section_id}
Section Title: {req.section_title}
Section Intent Hint: {req.section_intent_hint or "None"}
Required Outputs: {req.required_outputs}
User Focus: {req.user_focus or "None"}
Time Horizon: {req.time_horizon or "Not specified"}
Extra Context: {json.dumps(req.extra_context, ensure_ascii=False)}

BACKGROUND REPORTS:
{background or "No background provided."}

EXTRACTED BACKGROUND:
{json.dumps(extracted_background, ensure_ascii=False, indent=2)}

OPTIONAL LIGHT GROUNDING NOTES:
{grounding_notes or "None"}

TASK:
1. Identify the analytical purpose of this section.
2. Extract section-relevant assumptions, controversies, model drivers, and evidence gaps from the background.
3. Generate exactly one root question for this section.
4. Generate 3 to 7 mandatory sub-questions (level 1).
5. Generate sub-sub-questions only if they are necessary for evidence collection.
6. Every question must be concrete, researchable, and evidence-seeking.
7. Map every required_output to at least one question node in coverage_map.
8. Provide execution_order from highest priority to lowest priority.
9. Provide data_quality_flags if the input background is incomplete, duplicated, stale, truncated, or internally inconsistent.
10. Do not write final prose.
11. Do not invent verified facts. If a fact is uncertain or only suggested by background, mark it as "needs verification".
12. The plan should be usable by downstream research agents.

Return STRICT JSON matching this schema example:
{json.dumps(schema_hint, ensure_ascii=False, indent=2)}
""".strip()
