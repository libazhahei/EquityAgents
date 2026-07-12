"""Session blackboard — shared notes within a single section research session.

The blackboard allows PER nodes (planner/executor/synthesizer/reflector) to share
intermediate findings, hypotheses, contradictions, and cross-question hints without
polluting long-term ledgers or parent state.

Lifecycle:
- Initialized empty at section research session start
- Appended to by synthesizer (leftover evidence) and reflector (coverage insights)
- Read by all PER nodes via `format_blackboard_for_prompt()`
- Session end: full content persisted to BlackboardStore; summary injected to later sessions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


# Core tags for filtering — can be extended with free-form tags
BLACKBOARD_CORE_TAGS: frozenset[str] = frozenset({
    "revenue", "margin", "growth", "valuation", "risk", "catalyst",
    "consensus", "assumption", "kpi", "guidance", "capex", "opex",
    "competitive", "regulatory", "macro", "liquidity", "leverage",
    "segment", "geography", "product", "customer", "supply_chain",
})

# Valid entry types
BLACKBOARD_ENTRY_TYPES: frozenset[str] = frozenset({
    "finding",         # Research finding (e.g., "NVDA data center revenue grew 40% YoY")
    "hypothesis",      # Temporary hypothesis (e.g., "margin compression is mix-shift driven")
    "contradiction",   # Discovered contradiction (e.g., "10-K says X, earnings call says Y")
    "cross_question",  # Hint useful for other questions in the section
    "methodology",     # Research methodology note (e.g., "SEC filings for this ticker lag by 2 quarters")
    "data_pointer",    # Data source pointer (e.g., "IR page has better segment breakdown")
})


class BlackboardEntry(BaseModel):
    """A single blackboard entry — a session-scoped research note."""

    entry_id: str = Field(default_factory=lambda: f"bb_{uuid.uuid4().hex[:12]}")
    section_id: str = ""
    question_id: str | None = None
    source_node: str = ""  # "synthesizer" | "reflector"
    entry_type: str = "finding"
    content: str = ""
    tags: list[str] = Field(default_factory=list)
    confidence: float = 0.5
    superseded_by: str | None = None
    created_at_iteration: int = 0
    related_evidence_ids: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def model_post_init(self, __context: Any) -> None:
        # Normalize tags to lowercase
        self.tags = [t.lower().strip() for t in self.tags if t.strip()]
        # Validate entry_type
        if self.entry_type not in BLACKBOARD_ENTRY_TYPES:
            # Allow unknown types but warn — keeps forward compatibility
            pass


def blackboard_reducer(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append-only reducer with entry_id dedup and in-place update support."""
    if not new:
        return list(existing) if existing else []
    result = list(existing) if existing else []
    existing_ids = {e.get("entry_id") for e in result if e.get("entry_id")}
    for entry in new:
        eid = entry.get("entry_id")
        if eid and eid in existing_ids:
            # Update in place (e.g., confidence bump, supersede link)
            for i, e in enumerate(result):
                if e.get("entry_id") == eid:
                    result[i] = {**e, **entry}
                    break
        else:
            result.append(entry)
            if eid:
                existing_ids.add(eid)
    return result


def format_blackboard_for_prompt(
    entries: list[dict] | list[BlackboardEntry],
    *,
    max_items: int = 10,
    max_chars: int = 1500,
    filter_tags: list[str] | None = None,
    filter_types: list[str] | None = None,
    section_id: str | None = None,
) -> str:
    """Format blackboard entries for injection into a node prompt.

    Args:
        entries: List of blackboard entry dicts or BlackboardEntry models
        max_items: Maximum number of entries to include
        max_chars: Maximum total character count
        filter_tags: If provided, only include entries with at least one matching tag
        filter_types: If provided, only include entries of these types
        section_id: If provided, only include entries from this section

    Returns:
        Formatted markdown string, or empty string if no entries match
    """
    if not entries:
        return ""

    # Normalize to dicts
    items: list[dict] = []
    for e in entries:
        if isinstance(e, BlackboardEntry):
            items.append(e.model_dump())
        elif isinstance(e, dict):
            items.append(e)
        else:
            continue

    # Filter by section
    if section_id:
        items = [e for e in items if e.get("section_id") == section_id or not e.get("section_id")]

    # Filter by tags
    if filter_tags:
        filter_tags_lower = {t.lower() for t in filter_tags}
        items = [
            e for e in items
            if filter_tags_lower.intersection(set(e.get("tags", [])))
        ]

    # Filter by type
    if filter_types:
        filter_types_set = set(filter_types)
        items = [e for e in items if e.get("entry_type") in filter_types_set]

    if not items:
        return ""

    # Sort by iteration (desc), then by created_at (desc)
    items.sort(key=lambda e: (e.get("created_at_iteration", 0), e.get("created_at", "")), reverse=True)

    # Take top N
    items = items[:max_items]

    # Format as markdown bullets
    lines: list[str] = []
    total_chars = 0
    for entry in items:
        entry_type = entry.get("entry_type", "finding")
        iteration = entry.get("created_at_iteration", 0)
        content = entry.get("content", "")
        tags = entry.get("tags", [])
        confidence = entry.get("confidence", 0.5)

        # Truncate long content
        if len(content) > 200:
            content = content[:197] + "..."

        tags_str = f" (tags: {', '.join(tags[:3])})" if tags else ""
        line = f"- [{entry_type}, iter={iteration}] {content}{tags_str}"

        if total_chars + len(line) > max_chars:
            break
        lines.append(line)
        total_chars += len(line)

    if not lines:
        return ""

    return "## Session Blackboard (Recent Insights)\n" + "\n".join(lines)


def extract_tags_from_text(text: str) -> list[str]:
    """Extract core tags from text by keyword matching.

    Used by auto-write paths to assign tags based on content.
    """
    text_lower = text.lower()
    tag_keywords: dict[str, list[str]] = {
        "revenue": ["revenue", "sales", "top line", "top-line"],
        "margin": ["margin", "gross margin", "operating margin", "ebitda margin"],
        "growth": ["growth", "cagr", "yoy", "year-over-year", "qoq"],
        "valuation": ["valuation", "pe ratio", "ev/ebitda", "multiple", "dcf"],
        "risk": ["risk", "downside", "threat", "headwind"],
        "catalyst": ["catalyst", "trigger", "event"],
        "consensus": ["consensus", "street", "analyst", "estimate"],
        "assumption": ["assumption", "assumed", "project"],
        "kpi": ["kpi", "metric", "indicator", "ratio"],
        "guidance": ["guidance", "outlook", "forecast", "forward-looking"],
        "capex": ["capex", "capital expenditure", "capex intensity"],
        "opex": ["opex", "operating expense", "sga", "r&d"],
        "competitive": ["competitive", "competitor", "market share", "peer"],
        "regulatory": ["regulatory", "regulation", "compliance", "legal"],
        "macro": ["macro", "interest rate", "inflation", "gdp", "recession"],
        "segment": ["segment", "business line", "division"],
        "geography": ["geographic", "region", "country", "international"],
        "product": ["product", "service", "offering", "solution"],
        "customer": ["customer", "client", "end-user", "demand"],
        "supply_chain": ["supply chain", "supplier", "sourcing", "logistics"],
    }
    found: list[str] = []
    for tag, keywords in tag_keywords.items():
        if any(kw in text_lower for kw in keywords):
            found.append(tag)
    return found
