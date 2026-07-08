"""Compile phase — render the parameter registry into a text grid.

The grid is injected into synthesizer and reflector prompts to give them
full-fidelity access to structured parameters without any lossy compression.
"""

from __future__ import annotations

from tradingagents.equity_research.runtime.parameter_schemas import ParameterRegistry

# Maximum history versions rendered per parameter (oldest truncated first).
_MAX_HISTORY_RENDERED = 3


def compile_parameter_grid(
    registry: ParameterRegistry,
    question_id: str | None = None,
) -> str:
    """Render a human-readable parameter grid from the registry.

    No length cap — the design decision is to preserve all data.
    """
    lines: list[str] = ["[🔒 Parameter Grid — full-fidelity, do not truncate]"]

    params = list(registry.parameters.values())
    if question_id:
        params = [p for p in params if p.question_id in (question_id, "general")]

    if not params:
        return lines[0] + "\n(no parameters extracted)"

    # Group by dimension
    by_dimension: dict[str, list] = {}
    for param in params:
        dim = param.dimension or "general"
        by_dimension.setdefault(dim, []).append(param)

    for dim, dim_params in by_dimension.items():
        lines.append(f"\n## {dim}")

        normal = [p for p in dim_params if not p.is_conflict]
        conflicts = [p for p in dim_params if p.is_conflict]

        for param in normal:
            line = f"- {param.key}: {param.current.value}"
            if param.current.unit:
                line += f" {param.current.unit}"
            line += f" (as of: {param.current.as_of})"
            if param.current.source:
                line += f" — {param.current.source}"
            lines.append(line)

            if param.history:
                for h in param.history[-_MAX_HISTORY_RENDERED:]:
                    unit = f" {h.unit}" if h.unit else ""
                    lines.append(
                        f"  ↳ {h.value}{unit} (as of: {h.as_of}, iter {h.turn})"
                    )

        if conflicts:
            lines.append("\n⚠️ Conflicts:")
            for param in conflicts:
                lines.append(f"- {param.key}:")
                c = param.current
                unit = f" {c.unit}" if c.unit else ""
                lines.append(
                    f"  * Current: {c.value}{unit} (as of: {c.as_of}, source: {c.source})"
                )
                for h in param.history[-_MAX_HISTORY_RENDERED:]:
                    h_unit = f" {h.unit}" if h.unit else ""
                    lines.append(
                        f"  * History: {h.value}{h_unit} (as of: {h.as_of}, source: {h.source})"
                    )

    return "\n".join(lines)
