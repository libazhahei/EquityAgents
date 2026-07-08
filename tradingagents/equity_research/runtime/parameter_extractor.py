"""Map phase — LLM-driven parameter extraction from evidence.

Given a batch of evidence items and a skill context, the extractor invokes
the LLM with a structured-output schema (LLMExtractionOutput) to produce
a list of Parameter objects ready for reduction.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.parameter_schemas import (
    ExtractedParameter,
    LLMExtractionOutput,
    Parameter,
    ParameterValue,
)
from tradingagents.equity_research.runtime.skill_parameter_parser import (
    build_extraction_prompt_template,
    extract_parameter_dimensions,
)
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)

logger = logging.getLogger(__name__)



def extract_parameters_from_evidence(
    deps: EquityResearchDeps,
    evidence_items: list[dict],
    skill_context: dict[str, Any],
    question_id: str = "general",
    current_turn: int = 0,
) -> tuple[list[Parameter], str]:
    """Batch-extract structured parameters from a list of evidence items.

    Returns a ``(parameters, unstructured_narrative)`` tuple.  On LLM or
    structured-output failure, returns an empty list and logs a warning.
    """
    if not evidence_items:
        return [], ""

    # 1. Derive dimensions from skill context
    dimensions = extract_parameter_dimensions(skill_context)
    constraints = skill_context.get("constraints", "")

    # 2. Build the extraction prompt
    prompt_template = build_extraction_prompt_template(dimensions, constraints)
    evidence_text = _format_evidence_for_extraction(evidence_items)

    full_prompt = (
        f"{prompt_template}\n"
        f"Evidence list:\n{evidence_text}\n\n"
        f"Output JSON conforming to LLMExtractionOutput."
    )

    # 3. Invoke LLM with structured output
    try:
        result = invoke_structured_with_retry(
            deps.quick_llm,
            LLMExtractionOutput,
            full_prompt,
            agent_name="parameter_extractor",
            fallback=lambda: LLMExtractionOutput(),
        )
    except StructuredOutputUnsupported:
        logger.warning("parameter_extractor: structured output unsupported; skipping extraction")
        return [], ""
    except Exception as exc:
        logger.warning("parameter_extractor: extraction failed (%s)", exc)
        return [], ""

    # 4. Convert to Parameter objects
    parameters: list[Parameter] = []
    for extracted in result.parameters:
        as_of = extracted.as_of or "unknown"

        source = _find_source_for_evidence(extracted, evidence_items)
        evidence_id = _find_evidence_id(extracted, evidence_items)

        param = Parameter(
            key=extracted.key,
            dimension=extracted.dimension or _infer_dimension(extracted.key, dimensions),
            current=ParameterValue(
                value=extracted.value,
                unit=extracted.unit,
                as_of=as_of,
                turn=current_turn,
                source=source,
                evidence_id=evidence_id,
                confidence=extracted.confidence,
                raw_snippet=extracted.context,
            ),
            source_evidence_ids=[evidence_id] if evidence_id else [],
            question_id=question_id,
        )
        parameters.append(param)

    return parameters, result.unstructured_narrative



_URL_PATTERN = re.compile(
    r"https?://\S+|www\.\S+"  # plain URLs
    r"|\[([^\]]+)\]\(https?://\S+\)"  # markdown links — keep link text
    r"|<https?://\S+>"  # angle-bracket URLs
)


def _strip_urls(text: str) -> str:
    """Remove URLs from *text*, preserving surrounding readable content.

    Handles plain ``http(s)://…`` URLs, markdown ``[text](url)`` links
    (keeping the link text), and angle-bracket URLs ``<url>``.
    """
    def _replace(m: re.Match) -> str:
        # Markdown link — keep the bracketed text (group 1)
        if m.group(1):
            return m.group(1)
        return ""

    cleaned = _URL_PATTERN.sub(_replace, text)
    # Collapse extra whitespace left behind
    cleaned = re.sub(r"  +", " ", cleaned)
    return cleaned.strip()


def _format_evidence_for_extraction(evidence_items: list[dict]) -> str:
    """Format evidence items into a numbered text block for the LLM.

    URLs are stripped from snippets so the LLM focuses on content only.
    """
    lines: list[str] = []
    for i, ev in enumerate(evidence_items, 1):
        lines.append(f"[{i}] {ev.get('source', 'unknown')}")
        lines.append(f"    evidence_id: {ev.get('evidence_id', '')}")
        snippet = _strip_urls(str(ev.get("snippet") or ev.get("content") or ""))
        lines.append(f"    snippet: {snippet}")
        lines.append("")
    return "\n".join(lines)


def _infer_dimension(key: str, dimensions: list[str]) -> str:
    """Best-effort dimension inference from parameter key.

    Tokenizes both the key and each dimension on underscores and checks
    for any shared token (excluding very short tokens like "a", "to").
    """
    key_tokens = {t for t in key.lower().split("_") if len(t) > 2}
    if not key_tokens:
        return "general"
    for dim in dimensions:
        dim_tokens = {t for t in dim.lower().split("_") if len(t) > 2}
        if key_tokens & dim_tokens:
            return dim
    return "general"


def _find_source_for_evidence(
    extracted: ExtractedParameter,
    evidence_items: list[dict],
) -> str:
    """Match extracted context back to the originating evidence source."""
    context = extracted.context
    if not context:
        return "unknown"
    for ev in evidence_items:
        if context in str(ev.get("snippet", "")):
            return ev.get("source", "unknown")
    return "unknown"


def _find_evidence_id(
    extracted: ExtractedParameter,
    evidence_items: list[dict],
) -> str:
    """Match extracted context back to the originating evidence ID."""
    context = extracted.context
    if not context:
        return ""
    for ev in evidence_items:
        if context in str(ev.get("snippet", "")):
            return ev.get("evidence_id", "")
    return ""
