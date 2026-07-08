"""Skill-driven parameter dimension extraction.

Parses skill.md context (prompt templates, constraints) to derive the set of
analysis dimensions that guide LLM parameter extraction. This ensures the
extractor targets the right metrics for each research skill.
"""

from __future__ import annotations

import re
from typing import Any


def extract_parameter_dimensions(skill_context: dict[str, Any]) -> list[str]:
    """Extract analysis dimensions from skill context.

    Sources:
    1. ``Required outputs`` section in ``prompt_template``
    2. Dimension-keyword patterns in ``constraints`` text
    """
    dimensions: list[str] = []

    # 1. From "Required outputs" list in prompt_template
    prompt = skill_context.get("prompt_template", "")
    if prompt:
        match = re.search(r"Required outputs:\s*\n((?:\d+\.\s+\w+.*\n?)+)", prompt)
        if match:
            outputs = re.findall(r"\d+\.\s+(\w+)", match.group(1))
            dimensions.extend(outputs)

    # 2. From dimension-keyword patterns in constraints
    constraints = skill_context.get("constraints", "")
    if constraints:
        patterns = re.findall(
            r"(\w*(?:_model|_metrics|_analysis|_estimate|_driver|_margin|_revenue|_growth|_valuation)\w*)",
            constraints,
        )
        dimensions.extend(patterns)

    return list(dict.fromkeys(dimensions))  # deduplicate, preserve order


def build_extraction_prompt_template(dimensions: list[str], constraints: str) -> str:
    """Build the LLM extraction prompt from skill-driven dimensions."""
    dim_list = "\n".join(f"- {d}" for d in dimensions) if dimensions else "- general"
    constraints_excerpt = constraints[:1000] if constraints else "(none provided)"
    return f"""Extract structured parameters from the evidence below.

Target dimensions (from the research skill definition):
{dim_list}

Research constraints:
{constraints_excerpt}

Requirements:
1. Extract every quantifiable metric relevant to the target dimensions.
2. Each parameter must include: key (snake_case), value, unit, as_of (time point such as FY2025 / Q3 2024 / 2025-03-15), context.
3. as_of is mandatory — infer the data time point from the evidence.
4. Place non-quantifiable narrative content in unstructured_narrative.
5. Do not truncate — extract all relevant parameters.
6. Estimate extraction confidence (0–1).
7. Assign each parameter to the most relevant dimension (or "general").
"""
