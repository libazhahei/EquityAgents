"""Live invoke adapter: run section research like demo_section_research.py."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from demo_section_research import (
    _build_deps,
    _load_background_json,
    _load_planner_json,
)
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.agents.research_loop.subgraph import (
    _map_section_research_result,
    create_run_section_research_subgraph,
)
from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.equity_research.tasks.section_research.profile import SECTION_RESEARCH_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.seed import seed_section_research_state
from tradingagents.equity_research.templates.report_template import MVP1_REPORT_TEMPLATE

from evaluation.section_research.evaluators.faithfulness import build_evidence_pack
from evaluation.section_research.types import EvalBundle, FixtureMeta

logger = logging.getLogger(__name__)


def _resolve_path(path: str | None, base: Path) -> Path | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def invoke_section_research(
    *,
    ticker: str,
    section_id: str,
    background_json: Path | None = None,
    planner_json: Path | None = None,
    max_iterations: int = 5,
    mode: str = "wrapper",
    quick_research: bool | None = None,
    skip_verify: bool | None = None,
) -> dict[str, Any]:
    """Invoke section research and return the demo-shaped result dict."""
    config = DEFAULT_CONFIG.copy()
    if quick_research is not None:
        config.setdefault("equity_research", {})["quick_research"] = bool(quick_research)
    if skip_verify is not None:
        config.setdefault("equity_research", {})["skip_verify"] = bool(skip_verify)
    deps = _build_deps(config)

    state = empty_equity_research_state()
    state.update({
        "ticker": ticker.upper(),
        "sector": "",
        "documents": [],
        "api_calls": 0,
        "max_section_research_iterations": max_iterations,
        "max_research_iterations": max_iterations,
        "active_section_id": section_id,
    })

    if background_json and background_json.exists():
        state.update(_load_background_json(background_json))
        logger.info("Loaded background from %s", background_json)
    if planner_json and planner_json.exists():
        state.update(_load_planner_json(planner_json))
        logger.info("Loaded planner from %s", planner_json)

    if not state.get("ticker"):
        state["ticker"] = ticker.upper()

    section_plan = (state.get("section_plans") or {}).get(section_id, {})
    if not section_plan:
        template = MVP1_REPORT_TEMPLATE.get(section_id, {})
        section_plan = {
            "section_id": section_id,
            "section_title": template.get("title", section_id),
            "root_question": f"What should the {section_id} section cover for {state['ticker']}?",
            "planning_thesis": template.get("intent_hint", ""),
            "nodes": [],
        }
        state.setdefault("section_plans", {})[section_id] = section_plan

    if mode == "subgraph":
        compiled = SectionResearchSubgraph(deps, SECTION_RESEARCH_TASK_PROFILE).compile()
        subgraph_input = seed_section_research_state(
            state,
            SECTION_RESEARCH_TASK_PROFILE,
            section_id=section_id,
            section_plan=section_plan,
        )
        subgraph_input["max_iterations"] = max_iterations
        raw = compiled.invoke(subgraph_input)
        mapped = _map_section_research_result(
            deps, state, raw, SECTION_RESEARCH_TASK_PROFILE, section_id=section_id,
        )
    else:
        run = create_run_section_research_subgraph(deps)
        mapped = run(state)

    section_out = (mapped.get("section_research_outputs") or {}).get(section_id) or {}
    return {
        "ticker": state["ticker"],
        "section_id": section_id,
        **mapped,
        "section_research_output": section_out,
        "parameter_registry": section_out.get("parameter_registry")
        or mapped.get("parameter_registry")
        or {},
        "parameter_grid": section_out.get("parameter_grid") or mapped.get("parameter_grid") or "",
    }


def bundle_from_live(
    fixture: FixtureMeta,
    *,
    dataset_dir: Path,
    quick_research: bool | None = None,
    skip_verify: bool | None = None,
) -> EvalBundle:
    bg = _resolve_path(fixture.background_json, dataset_dir)
    planner = _resolve_path(fixture.planner_json, dataset_dir)
    result = invoke_section_research(
        ticker=fixture.ticker,
        section_id=fixture.section_id,
        background_json=bg,
        planner_json=planner,
        max_iterations=fixture.max_iterations,
        mode=fixture.mode,
        quick_research=quick_research,
        skip_verify=skip_verify,
    )
    return EvalBundle(
        ticker=str(result.get("ticker") or fixture.ticker).upper(),
        section_id=fixture.section_id,
        final_state=result,
        child_runs=[],
        evidence=build_evidence_pack(result),
        fixture_meta=fixture,
        source="live",
    )
