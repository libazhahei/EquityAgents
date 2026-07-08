"""Map phase — LLM-driven parameter extraction from evidence.

Given a batch of evidence items and a skill context, the extractor invokes
the LLM with a structured-output schema (LLMExtractionOutput) to produce
a list of Parameter objects ready for reduction.

When the total evidence text exceeds 6000 characters, individual snippets are
compacted via :func:`compact_if_needed` before extraction.  When there are
more than 3 evidence items, extraction is split into parallel batches (max 3
items each) processed concurrently with :class:`ThreadPoolExecutor`.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from tradingagents.equity_research.runtime.utils.context_compact import (
    compact_if_needed,
)
from tradingagents.equity_research.runtime.utils.structured_invoke import (
    StructuredOutputUnsupported,
    invoke_structured_with_retry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXTRACT_MAX_CHARS = 6000
_EXTRACT_BATCH_SIZE = 3


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_parameters_from_evidence(
    deps: EquityResearchDeps,
    evidence_items: list[dict],
    skill_context: dict[str, Any],
    question_id: str = "general",
    current_turn: int = 0,
) -> tuple[list[Parameter], str]:
    """Batch-extract structured parameters from a list of evidence items.

    Processing pipeline:
    1. Strip URLs from evidence snippets.
    2. Compact individual snippets (via LLM) if total text > 6000 chars.
    3. Split into batches of max 3 items.
    4. Process batches in parallel with ``ThreadPoolExecutor``.
    5. Merge all extracted parameters and narratives.

    Returns a ``(parameters, unstructured_narrative)`` tuple.  On LLM or
    structured-output failure, returns an empty list and logs a warning.
    """
    if not evidence_items:
        return [], ""

    # 1. Derive dimensions from skill context
    dimensions = extract_parameter_dimensions(skill_context)
    constraints = skill_context.get("constraints", "")

    # 2. Strip URLs from all evidence snippets (in-place on shallow copies)
    cleaned_items = _strip_urls_from_evidence(evidence_items)

    # 3. Compact snippets if total evidence text is too long
    cleaned_items = _compact_evidence_if_needed(deps, cleaned_items, _EXTRACT_MAX_CHARS)

    # 4. Build the shared prompt template
    prompt_template = build_extraction_prompt_template(dimensions, constraints)

    # 5. Split into batches and process in parallel
    batches = _split_into_batches(cleaned_items, _EXTRACT_BATCH_SIZE)
    all_parameters: list[Parameter] = []
    narratives: list[str] = []

    if len(batches) == 1:
        # Single batch — no need for thread pool overhead
        params, narrative = _extract_single_batch(
            deps, batches[0], prompt_template, question_id, current_turn, cleaned_items,
        )
        all_parameters.extend(params)
        if narrative:
            narratives.append(narrative)
    else:
        logger.info(
            "parameter_extractor: processing %d evidence items in %d parallel batches",
            len(cleaned_items), len(batches),
        )
        with ThreadPoolExecutor(max_workers=len(batches)) as pool:
            futures = {
                pool.submit(
                    _extract_single_batch,
                    deps, batch, prompt_template, question_id, current_turn, cleaned_items,
                ): idx
                for idx, batch in enumerate(batches)
            }
            results_by_idx: dict[int, tuple[list[Parameter], str]] = {}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    results_by_idx[idx] = future.result()
                except Exception as exc:
                    logger.warning("parameter_extractor: batch %d failed (%s)", idx, exc)
                    results_by_idx[idx] = ([], "")

        # Merge in order
        for idx in sorted(results_by_idx):
            params, narrative = results_by_idx[idx]
            all_parameters.extend(params)
            if narrative:
                narratives.append(narrative)

    combined_narrative = "\n\n".join(narratives) if narratives else ""
    return all_parameters, combined_narrative


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_single_batch(
    deps: EquityResearchDeps,
    batch: list[dict],
    prompt_template: str,
    question_id: str,
    current_turn: int,
    all_evidence: list[dict],
) -> tuple[list[Parameter], str]:
    """Run LLM extraction on a single batch of evidence items.

    *all_evidence* is the full (URL-stripped, compacted) evidence list used
    for matching extracted context back to evidence IDs / sources.
    """
    evidence_text = _format_evidence_for_extraction(batch)
    full_prompt = (
        f"{prompt_template}\n"
        f"Evidence list:\n{evidence_text}\n\n"
        f"Output JSON conforming to LLMExtractionOutput."
    )

    try:
        result = invoke_structured_with_retry(
            deps.quick_llm,
            LLMExtractionOutput,
            full_prompt,
            agent_name="parameter_extractor",
            fallback=lambda: LLMExtractionOutput(),
        )
    except StructuredOutputUnsupported:
        logger.warning("parameter_extractor: structured output unsupported; skipping batch")
        return [], ""
    except Exception as exc:
        logger.warning("parameter_extractor: batch extraction failed (%s)", exc)
        return [], ""

    parameters: list[Parameter] = []
    dimensions = _dimensions_from_prompt_template(prompt_template)

    for extracted in result.parameters:
        as_of = extracted.as_of or "unknown"
        source = _find_source_for_evidence(extracted, all_evidence)
        evidence_id = _find_evidence_id(extracted, all_evidence)

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


def _dimensions_from_prompt_template(prompt_template: str) -> list[str]:
    """Re-extract dimension names from the already-built prompt template.

    The prompt template contains lines like ``- dimension_name`` under
    "Target dimensions".  This is a lightweight fallback for
    ``_infer_dimension`` when running in a thread without direct access to
    ``skill_context``.
    """
    dims: list[str] = []
    in_section = False
    for line in prompt_template.split("\n"):
        if "Target dimensions" in line:
            in_section = True
            continue
        if in_section:
            line = line.strip()
            if line.startswith("- "):
                dims.append(line[2:].strip())
            elif line and not line.startswith("-") and dims:
                break  # end of dimension list
    return dims


def _strip_urls_from_evidence(evidence_items: list[dict]) -> list[dict]:
    """Return shallow copies of evidence items with URLs stripped from snippets."""
    cleaned: list[dict] = []
    for ev in evidence_items:
        ev_copy = dict(ev)
        for field in ("snippet", "content"):
            val = ev_copy.get(field)
            if isinstance(val, str) and val:
                ev_copy[field] = _strip_urls(val)
        cleaned.append(ev_copy)
    return cleaned


def _compact_evidence_if_needed(
    deps: EquityResearchDeps,
    evidence_items: list[dict],
    max_chars: int,
) -> list[dict]:
    """Compact evidence snippets via LLM if total text exceeds *max_chars*.

    Each snippet receives a proportional character budget
    (``max_chars / len(evidence_items)``).  :func:`compact_if_needed` handles
    the actual compaction — snippets already within budget are returned
    unchanged.
    """
    total_chars = sum(
        len(str(ev.get("snippet") or ev.get("content") or ""))
        for ev in evidence_items
    )
    if total_chars <= max_chars:
        return evidence_items

    num_items = len(evidence_items)
    per_snippet_budget = max(max_chars // max(num_items, 1), 500)

    compacted: list[dict] = []
    for i, ev in enumerate(evidence_items):
        ev_copy = dict(ev)
        for field in ("snippet", "content"):
            text = ev_copy.get(field)
            if isinstance(text, str) and text:
                ev_copy[field] = compact_if_needed(
                    deps,
                    text,
                    purpose=f"evidence_snippet_{i + 1}_of_{num_items}",
                    max_chars=per_snippet_budget,
                )
        compacted.append(ev_copy)

    logger.info(
        "parameter_extractor: compacted %d snippets (total %d chars → budget %d per snippet)",
        num_items, total_chars, per_snippet_budget,
    )
    return compacted


def _split_into_batches(items: list[dict], batch_size: int) -> list[list[dict]]:
    """Split *items* into sub-lists of at most *batch_size* elements."""
    return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]


# ---------------------------------------------------------------------------
# URL stripping
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Dimension inference & evidence matching
# ---------------------------------------------------------------------------


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
