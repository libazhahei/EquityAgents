"""Merge utilities for assumption view updates."""

from __future__ import annotations

from tradingagents.equity_research.runtime.utils.dedupe import (
    find_similar_index,
    merge_list_by_similarity,
    similarity,
)
from tradingagents.equity_research.state.consensus_schemas import ConflictRecord, CoverageStatus
from tradingagents.equity_research.tasks.assumption.schemas import (
    AssumptionItem,
    AssumptionView,
    AssumptionViewUpdate,
    ResearchSuggestion,
)

_COVERAGE_ORDER = {
    CoverageStatus.EMPTY: 0,
    CoverageStatus.PARTIAL: 1,
    CoverageStatus.SUFFICIENT: 2,
    CoverageStatus.STRONG: 3,
}


def _merge_coverage(old: CoverageStatus | str | None, new: CoverageStatus | str | None) -> CoverageStatus:
    if isinstance(old, str):
        try:
            old = CoverageStatus(old)
        except ValueError:
            old = CoverageStatus.EMPTY
    if isinstance(new, str):
        try:
            new = CoverageStatus(new)
        except ValueError:
            new = CoverageStatus.EMPTY
    if old is None:
        return new or CoverageStatus.EMPTY
    if new is None:
        return old
    return new if _COVERAGE_ORDER.get(new, 0) > _COVERAGE_ORDER.get(old, 0) else old


def _merge_assumption_items(existing: list[AssumptionItem], incoming: list[AssumptionItem]) -> list[AssumptionItem]:
    by_id: dict[str, AssumptionItem] = {item.id: item for item in existing if item.id}
    merged = list(existing)

    for item in incoming:
        if item.id and item.id in by_id:
            current = by_id[item.id]
            data = current.model_dump()
            upd = item.model_dump(exclude_unset=True)
            for key, value in upd.items():
                if value is None:
                    continue
                if isinstance(value, list) and isinstance(data.get(key), list):
                    existing_list = data.get(key) or []
                    if value and all(isinstance(x, str) for x in value) and all(
                        isinstance(x, str) for x in existing_list
                    ):
                        data[key] = merge_list_by_similarity(list(existing_list), list(value))
                    else:
                        data[key] = list(dict.fromkeys([*existing_list, *value]))
                elif isinstance(value, str) and data.get(key):
                    if value and value != data[key]:
                        data.setdefault("evidence_against", [])
                        if value not in data["evidence_against"]:
                            data["evidence_against"].append(value)
                else:
                    data[key] = value
            replacement = AssumptionItem.model_validate(data)
            merged = [replacement if x.id == item.id else x for x in merged]
            by_id[item.id] = replacement
            continue

        duplicate = False
        for prev in merged:
            if similarity(item.statement, prev.statement) >= 0.85:
                duplicate = True
                break
        if not duplicate:
            merged.append(item)
            if item.id:
                by_id[item.id] = item
    return merged


def _merge_suggestions(
    existing: list[ResearchSuggestion],
    incoming: list[ResearchSuggestion],
) -> list[ResearchSuggestion]:
    merged = list(existing)
    for item in incoming:
        match_idx = find_similar_index(
            [prev.direction for prev in merged],
            item.direction,
        )
        if match_idx is None:
            merged.append(item)
            continue
        prev = merged[match_idx]
        merged[match_idx] = ResearchSuggestion(
            direction=prev.direction,
            rationale=(prev.rationale + " " + item.rationale).strip()[:500],
            priority=min(prev.priority, item.priority),
            related_assumption=prev.related_assumption or item.related_assumption,
            related_assumptions=list(dict.fromkeys([*prev.related_assumptions, *item.related_assumptions])),
            next_checks=list(dict.fromkeys([*prev.next_checks, *item.next_checks])),
        )
    return merged


def merge_assumption_view(view: AssumptionView, update: AssumptionViewUpdate) -> AssumptionView:
    data = view.model_dump()

    if update.assumption_map is not None:
        data["assumption_map"] = [
            item.model_dump() for item in _merge_assumption_items(view.assumption_map, update.assumption_map)
        ]

    if update.conflicts is not None:
        existing = list(view.conflicts)
        existing.extend(update.conflicts)
        data["conflicts"] = [c.model_dump() for c in existing]

    if update.research_suggestions is not None:
        data["research_suggestions"] = [
            s.model_dump() for s in _merge_suggestions(view.research_suggestions, update.research_suggestions)
        ]

    if update.top_research_priorities is not None:
        data["top_research_priorities"] = merge_list_by_similarity(
            list(view.top_research_priorities),
            list(update.top_research_priorities),
        )

    if update.open_questions is not None:
        data["open_questions"] = merge_list_by_similarity(view.open_questions, update.open_questions)

    if update.watchlist is not None:
        data["watchlist"] = merge_list_by_similarity(view.watchlist, update.watchlist)

    if update.dimension_coverage is not None:
        coverage = dict(view.dimension_coverage)
        for dim, status in update.dimension_coverage.items():
            coverage[dim] = _merge_coverage(coverage.get(dim), status)
        data["dimension_coverage"] = {k: v.value if hasattr(v, "value") else v for k, v in coverage.items()}

    if update.coverage_score is not None:
        data["coverage_score"] = max(view.coverage_score, update.coverage_score)

    if update.source_doc_ids is not None:
        data["source_doc_ids"] = list(dict.fromkeys([*view.source_doc_ids, *update.source_doc_ids]))

    return AssumptionView.model_validate(data)
