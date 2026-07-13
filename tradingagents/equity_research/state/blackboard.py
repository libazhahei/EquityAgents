"""Session blackboard — shared notes within a single section research session.

The blackboard allows PER nodes (planner/executor/synthesizer/reflector) to share
intermediate findings, hypotheses, contradictions, and cross-question hints without
polluting long-term ledgers or parent state.

Lifecycle:
- Initialized empty at section research session start
- Appended primarily by reflector (coverage gaps / contradictions); synthesizer
  evidence echo is off by default (``blackboard_synthesizer_auto_write``)
- Read by planner/executor via `format_blackboard_for_prompt()`
- Session end: full content persisted to BlackboardStore; summary injected to later sessions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from tradingagents.equity_research.memory.similarity import text_similarity

# Max auto-written notes per reflector pass (Category-B style cap).
BLACKBOARD_COVERAGE_EXTRACT_MAX = 5


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
    """Append-only reducer with entry_id upsert and Jaccard near-dup skip on content."""
    _jaccard = 0.85

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
            continue
        content = str(entry.get("content") or "")
        entry_type = str(entry.get("entry_type") or "finding")
        if content and any(
            str(e.get("entry_type") or "finding") == entry_type
            and text_similarity(content, str(e.get("content") or "")) >= _jaccard
            for e in result
        ):
            continue  # near-dup — first-seen wins
        result.append(entry)
        if eid:
            existing_ids.add(eid)
    return result


def format_blackboard_for_prompt(
    entries: list[dict] | list[BlackboardEntry],
    *,
    max_items: int = 10,
    max_chars: int | None = None,
    filter_tags: list[str] | None = None,
    filter_types: list[str] | None = None,
    section_id: str | None = None,
) -> str:
    """Format blackboard entries for injection into a node prompt.

    Keeps Category-B item caps (``max_items``). Does not hard-truncate entry
    content; ``max_chars`` is retained for API compatibility but ignored —
    callers should fold this block into ``assemble_and_compact_context``.
    """
    del max_chars  # intentionally unused; no hard truncation
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

    # Take top N (Category B item cap)
    items = items[:max_items]

    lines: list[str] = []
    for entry in items:
        entry_type = entry.get("entry_type", "finding")
        iteration = entry.get("created_at_iteration", 0)
        content = entry.get("content", "")
        tags = entry.get("tags", [])
        tags_str = f" (tags: {', '.join(tags[:3])})" if tags else ""
        lines.append(f"- [{entry_type}, iter={iteration}] {content}{tags_str}")

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


def synthesizer_blackboard_auto_write_enabled(config: dict[str, Any] | None) -> bool:
    """Whether synthesizer may echo pending evidence onto the session blackboard.

    Default is False — evidence echo was measured as unused noise. Opt in via
    ``equity_research.blackboard_synthesizer_auto_write: true``.
    """
    if not isinstance(config, dict):
        return False
    er = config.get("equity_research")
    if not isinstance(er, dict):
        return False
    return bool(er.get("blackboard_synthesizer_auto_write", False))


def _report_field(report: Any, name: str, default: Any = None) -> Any:
    if report is None:
        return default
    if isinstance(report, dict):
        return report.get(name, default)
    return getattr(report, name, default)


def _gap_text_and_label(gap: Any) -> tuple[str, str]:
    if isinstance(gap, dict):
        text = str(
            gap.get("description")
            or gap.get("gap")
            or gap.get("message")
            or gap.get("issue")
            or ""
        ).strip()
        if not text:
            text = str(gap).strip()
        label = str(
            gap.get("label")
            or gap.get("dimension")
            or gap.get("coverage_output")
            or gap.get("type")
            or ""
        ).strip()
        return text, label
    return str(gap).strip(), ""


def _is_severe_data_quality_issue(issue: Any) -> bool:
    if not isinstance(issue, dict):
        return False
    severity = str(issue.get("severity") or "").strip().lower()
    if severity in {"high", "critical", "severe"}:
        return True
    # Numeric severities occasionally appear in older payloads.
    try:
        if float(issue.get("severity")) >= 0.7:
            return True
    except (TypeError, ValueError):
        pass
    return False


def _make_coverage_entry(
    *,
    section_id: str,
    entry_type: str,
    content: str,
    tags: list[str],
    confidence: float,
    iteration: int,
) -> dict[str, Any]:
    return BlackboardEntry(
        section_id=section_id,
        source_node="reflector",
        entry_type=entry_type,
        content=content[:300],
        tags=tags[:5],
        confidence=confidence,
        created_at_iteration=iteration,
    ).model_dump()


def extract_blackboard_entries_from_coverage(
    state: dict[str, Any],
    report: Any,
    iteration: int,
    *,
    max_entries: int = BLACKBOARD_COVERAGE_EXTRACT_MAX,
) -> list[dict[str, Any]]:
    """Rule-extract blackboard notes from a coverage / reflector report.

    Priority (until ``max_entries``):
    1. ``contradictions`` → ``contradiction``
    2. ``critical_gaps`` → ``methodology``
    3. severe ``data_quality_issues`` → ``finding``
    4. ``suggested_focus`` → ``hypothesis`` (consensus-style reports)
    5. low ``dimension_scores`` with notes → ``contradiction`` / ``finding``
    """
    if max_entries <= 0 or report is None:
        return []

    section_id = str(state.get("section_id") or "")
    entries: list[dict[str, Any]] = []

    def _remaining() -> int:
        return max_entries - len(entries)

    # 1) Contradictions
    for item in _report_field(report, "contradictions", []) or []:
        if _remaining() <= 0:
            break
        text, label = _gap_text_and_label(item)
        if len(text) < 10:
            continue
        content = f"Contradiction: {text}"
        if label:
            content = f"[{label}] {content}"
        tags = extract_tags_from_text(text)
        if label:
            tags = list(dict.fromkeys(tags + [label.lower().replace(" ", "_")]))
        entries.append(
            _make_coverage_entry(
                section_id=section_id,
                entry_type="contradiction",
                content=content,
                tags=tags,
                confidence=0.7,
                iteration=iteration,
            )
        )

    # 2) Critical gaps
    for gap in _report_field(report, "critical_gaps", []) or []:
        if _remaining() <= 0:
            break
        gap_text, gap_label = _gap_text_and_label(gap)
        if len(gap_text) < 10:
            continue
        content = f"Critical gap: {gap_text}"
        if gap_label:
            content = f"[{gap_label}] {content}"
        tags = extract_tags_from_text(gap_text)
        if gap_label:
            tags = list(dict.fromkeys(tags + [gap_label.lower().replace(" ", "_")]))
        entries.append(
            _make_coverage_entry(
                section_id=section_id,
                entry_type="methodology",
                content=content,
                tags=tags,
                confidence=0.6,
                iteration=iteration,
            )
        )

    # 3) Severe data-quality issues
    for issue in _report_field(report, "data_quality_issues", []) or []:
        if _remaining() <= 0:
            break
        if not _is_severe_data_quality_issue(issue):
            continue
        text, label = _gap_text_and_label(issue)
        if len(text) < 10:
            continue
        content = f"Data quality: {text}"
        if label:
            content = f"[{label}] {content}"
        tags = extract_tags_from_text(text)
        if label:
            tags = list(dict.fromkeys(tags + [label.lower().replace(" ", "_")]))
        entries.append(
            _make_coverage_entry(
                section_id=section_id,
                entry_type="finding",
                content=content,
                tags=tags,
                confidence=0.5,
                iteration=iteration,
            )
        )

    # 4) Suggested focus (consensus-style)
    if _remaining() > 0:
        suggested_focus = str(_report_field(report, "suggested_focus", "") or "").strip()
        if len(suggested_focus) > 20:
            tags = extract_tags_from_text(suggested_focus)
            entries.append(
                _make_coverage_entry(
                    section_id=section_id,
                    entry_type="hypothesis",
                    content=f"Reflector suggests: {suggested_focus}",
                    tags=tags,
                    confidence=0.4,
                    iteration=iteration,
                )
            )

    # 5) Low dimension scores with notes
    dimension_scores = _report_field(report, "dimension_scores", {}) or {}
    if isinstance(dimension_scores, dict):
        for dim_name, dim_data in dimension_scores.items():
            if _remaining() <= 0:
                break
            if isinstance(dim_data, dict):
                score = float(dim_data.get("score", 1.0))
                notes = str(dim_data.get("notes") or dim_data.get("gaps") or "").strip()
            else:
                try:
                    score = float(dim_data) if dim_data is not None else 1.0
                except (TypeError, ValueError):
                    score = 1.0
                notes = ""
            if score >= 0.4 or not notes:
                continue
            tags = extract_tags_from_text(f"{dim_name} {notes}")
            entries.append(
                _make_coverage_entry(
                    section_id=section_id,
                    entry_type="contradiction" if score < 0.2 else "finding",
                    content=f"Low coverage on {dim_name}: {notes}",
                    tags=tags,
                    confidence=0.3,
                    iteration=iteration,
                )
            )

    return entries[:max_entries]
