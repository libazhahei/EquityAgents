"""Parent-level human review gates (HR1 after assumption, HR2 after planner)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Literal

from tradingagents.equity_research.agents.deps import EquityResearchDeps


def load_human_review_json(path: str | Path) -> dict[str, Any]:
    """Load a combined HR1/HR2 JSON file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("human-review JSON must be an object")
    return data


def default_hr2_patch(config: dict[str, Any] | None = None) -> dict[str, Any]:
    er = (config or {}).get("equity_research", {}) if config else {}
    selected = er.get("default_selected_section_ids") or ["3_business_model"]
    return {"selected_section_ids": list(selected)}


def patches_for_interrupt(
    payload: dict[str, Any] | None,
    gate: Literal["human_review_1", "human_review_2"],
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the state update to apply before resuming a human-review interrupt."""
    payload = payload or {}
    section = payload.get(gate) or {}
    if not isinstance(section, dict):
        section = {}
    if gate == "human_review_1":
        return {"human_review_1_patch": section}
    patch = dict(section)
    if "selected_section_ids" not in patch:
        patch.update(default_hr2_patch(config))
    return {"human_review_2_patch": patch}


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base) if isinstance(base, dict) else {}
    for key, value in (patch or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _emit(deps: EquityResearchDeps, state: dict[str, Any], *, stage: str, status: str) -> None:
    bus = getattr(deps, "progress_bus", None)
    if bus is None:
        return
    bus.emit(
        stage=stage,
        node=stage,
        status=status,
        run_id=str(state.get("run_id", "")),
        thread_id=str(state.get("_thread_id", "")),
        ticker=str(state.get("ticker", "")),
    )


def create_human_review_1(deps: EquityResearchDeps):
    """Passthrough / apply consensus+assumption view patches."""

    def human_review_1(state: dict[str, Any]) -> dict[str, Any]:
        _emit(deps, state, stage="human_review_1", status="started")
        patch = state.get("human_review_1_patch") or {}
        updates: dict[str, Any] = {}
        if patch.get("consensus_view"):
            updates["consensus_view"] = _deep_merge(
                state.get("consensus_view") or {},
                patch["consensus_view"],
            )
        if patch.get("assumption_view"):
            updates["assumption_view"] = _deep_merge(
                state.get("assumption_view") or {},
                patch["assumption_view"],
            )
        # Allow full replacements via optional report fields
        for key in ("consensus_report", "assumption_report"):
            if key in patch:
                updates[key] = patch[key]
        status = "succeeded"
        _emit(deps, {**state, **updates}, stage="human_review_1", status=status)
        return updates

    return human_review_1


def create_human_review_2(deps: EquityResearchDeps):
    """Apply plan patches and ensure selected_section_ids (default section 3)."""

    def human_review_2(state: dict[str, Any]) -> dict[str, Any]:
        _emit(deps, state, stage="human_review_2", status="started")
        patch = state.get("human_review_2_patch") or {}
        updates: dict[str, Any] = {}

        if patch.get("section_plans"):
            updates["section_plans"] = _deep_merge(
                state.get("section_plans") or {},
                patch["section_plans"],
            )

        selected = patch.get("selected_section_ids")
        if not selected:
            selected = (state.get("selected_section_ids") or None) or default_hr2_patch(
                deps.config
            ).get("selected_section_ids")
        updates["selected_section_ids"] = list(selected)

        plans = updates.get("section_plans") or state.get("section_plans") or {}
        missing = [sid for sid in updates["selected_section_ids"] if sid not in plans]
        if missing:
            warnings = list(state.get("warnings") or [])
            warnings.append(
                f"human_review_2: selected sections missing from section_plans: {missing}"
            )
            updates["warnings"] = warnings

        _emit(deps, {**state, **updates}, stage="human_review_2", status="succeeded")
        return updates

    return human_review_2


def create_pick_next_section(deps: EquityResearchDeps):
    """Choose next selected section that lacks a research output."""

    def pick_next_section(state: dict[str, Any]) -> dict[str, Any]:
        selected = list(state.get("selected_section_ids") or [])
        if not selected:
            selected = list(default_hr2_patch(deps.config).get("selected_section_ids") or [])
        done = set((state.get("section_research_outputs") or {}).keys())
        for sid in selected:
            if sid not in done:
                return {
                    "active_section_id": sid,
                    "selected_section_ids": selected,
                    "research_status": "running",
                }
        return {
            "active_section_id": None,
            "selected_section_ids": selected,
            "research_status": "completed",
        }

    return pick_next_section
