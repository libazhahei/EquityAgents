"""Parameter-preserving schemas for structured evidence extraction.

Implements a version-chain model: each parameter carries a current value
plus an append-only history, enabling conflict detection and full traceability
across research iterations without destructive compression.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ParameterValue(BaseModel):
    """A single versioned snapshot of a parameter."""

    value: Any = Field(description="The parameter value (number, string, or list)")
    unit: str = Field(default="", description="Unit of measurement, e.g. '%', 'USD', 'x'")
    as_of: str = Field(
        description="Time context of the data point, e.g. 'FY2025', 'Q3 2024', '2025-03-15'"
    )
    turn: int = Field(default=0, description="Research iteration round")
    source: str = Field(default="", description="Evidence source label")
    evidence_id: str = Field(default="", description="Linked evidence ID")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    raw_snippet: str = Field(
        default="",
        description="Original evidence snippet — retained for full-fidelity audit",
    )


class Parameter(BaseModel):
    """A structured parameter with version chain and conflict tracking."""

    key: str = Field(description="Parameter key in snake_case, e.g. 'gross_margin'")
    dimension: str = Field(
        default="",
        description="Analysis dimension from the skill definition, e.g. 'margin_driver_analysis'",
    )
    current: ParameterValue
    history: list[ParameterValue] = Field(default_factory=list)
    source_evidence_ids: list[str] = Field(default_factory=list)
    question_id: str = Field(default="general")
    is_conflict: bool = Field(default=False)


class ParameterRegistry(BaseModel):
    """Global parameter registry — the single source of truth for extracted metrics."""

    parameters: dict[str, Parameter] = Field(default_factory=dict)
    dimensions: list[str] = Field(
        default_factory=list,
        description="Dimension list derived from skill.md",
    )
    last_updated: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ExtractedParameter(BaseModel):
    """A single parameter as extracted by the LLM (pre-reduction)."""

    key: str = Field(description="snake_case parameter key")
    value: Any = Field(description="Extracted value")
    unit: str = Field(default="", description="Unit of measurement")
    as_of: str = Field(
        description="Data time point, mandatory — e.g. 'FY2025', 'Q3 2024'"
    )
    context: str = Field(default="", description="Source text snippet")
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    dimension: str = Field(default="", description="Analysis dimension")


class LLMExtractionOutput(BaseModel):
    """Structured output from the LLM batch-extraction step."""

    parameters: list[ExtractedParameter] = Field(default_factory=list)
    unstructured_narrative: str = Field(
        default="",
        description="Narrative content that could not be structured",
    )
