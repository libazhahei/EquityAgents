"""Reduce phase — merge newly extracted parameters into the registry.

Handles semantic key matching (text similarity), conflict detection
(numeric tolerance), and version-chain append.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from tradingagents.equity_research.memory.similarity import text_similarity
from tradingagents.equity_research.runtime.parameter_schemas import (
    Parameter,
    ParameterRegistry,
)

logger = logging.getLogger(__name__)

# Key-similarity threshold for matching new parameters to existing entries.
_KEY_SIM_THRESHOLD = 0.85

# Numeric tolerance for conflict detection (5%).
_VALUE_TOLERANCE = 0.05


def reduce_parameters(
    existing_registry: ParameterRegistry,
    new_parameters: list[Parameter],
    current_turn: int,
) -> ParameterRegistry:
    """Merge *new_parameters* into *existing_registry*, returning an updated copy."""
    registry = existing_registry.model_copy(deep=True)

    for new_param in new_parameters:
        existing_key = _find_similar_parameter_key(registry, new_param.key)

        if existing_key:
            existing = registry.parameters[existing_key]

            if not _values_compatible(existing.current.value, new_param.current.value):
                # Conflict — different value for the same key
                existing.is_conflict = True
                existing.history.append(existing.current)
                existing.current = new_param.current
            else:
                # Same value — just record the additional observation
                existing.history.append(new_param.current)

            # Merge source evidence IDs
            merged_ids = list(
                dict.fromkeys(
                    existing.source_evidence_ids + new_param.source_evidence_ids
                )
            )
            existing.source_evidence_ids = merged_ids
        else:
            registry.parameters[new_param.key] = new_param

    # Update dimension list
    new_dims = [p.dimension for p in new_parameters if p.dimension]
    registry.dimensions = list(dict.fromkeys(registry.dimensions + new_dims))
    registry.last_updated = datetime.utcnow().isoformat()

    return registry


def _find_similar_parameter_key(
    registry: ParameterRegistry,
    candidate_key: str,
) -> str | None:
    """Return the first registry key whose text similarity exceeds the threshold."""
    for key in registry.parameters:
        if text_similarity(candidate_key, key) >= _KEY_SIM_THRESHOLD:
            return key
    return None


def _values_compatible(v1: Any, v2: Any) -> bool:
    """Return True if two values are equal within tolerance."""
    if isinstance(v1, (int, float)) and isinstance(v2, (int, float)):
        if v1 == 0 and v2 == 0:
            return True
        if v1 == 0 or v2 == 0:
            return abs(v1 - v2) < 1e-6
        relative_diff = abs(v1 - v2) / max(abs(v1), abs(v2))
        return relative_diff <= _VALUE_TOLERANCE
    return v1 == v2
