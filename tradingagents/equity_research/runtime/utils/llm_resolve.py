"""Resolve research LLM tier based on quick_research config."""

from __future__ import annotations

from typing import Any, Literal

ResearchLlmTier = Literal["deep", "quick", "nano"]


def is_quick_research(config: dict[str, Any] | None) -> bool:
    if not config:
        return True
    er = config.get("equity_research", {})
    return bool(er.get("quick_research", True))


def resolve_research_llm(deps: Any, tier: ResearchLlmTier) -> Any:
    if tier == "nano":
        return getattr(deps, "nano_llm", None) or deps.quick_llm
    if tier == "quick":
        return deps.quick_llm
    if is_quick_research(getattr(deps, "config", None)):
        return deps.quick_llm
    return deps.deep_llm
