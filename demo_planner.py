#!/usr/bin/env python3
"""Manual CLI demo for the section question tree planner.

For the full parent spine with durable checkpoints, see demo_equity_research.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.dynamic_planning import create_dynamic_planning
from tradingagents.equity_research.agents.section_planner.aggregate import planner_section_ids
from tradingagents.equity_research.agents.section_planner.state import (
    build_section_planner_request,
    empty_section_planner_state,
)
from tradingagents.equity_research.agents.section_planner.subgraph import SectionPlannerSubgraph
from tradingagents.equity_research.agents.task_analysis import create_analyze_research_task
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.llm_clients import create_llm_client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _build_deps(config: dict) -> EquityResearchDeps:
    set_config(config)
    llm_kwargs: dict = {}
    deep_client = create_llm_client(
        provider=config["llm_provider"],
        model=config["deep_think_llm"],
        base_url=config.get("backend_url"),
        **llm_kwargs,
    )
    quick_client = create_llm_client(
        provider=config["llm_provider"],
        model=config["quick_think_llm"],
        base_url=config.get("backend_url"),
        **llm_kwargs,
    )
    return EquityResearchDeps(
        config=config,
        deep_llm=deep_client.get_llm(),
        quick_llm=quick_client.get_llm(),
    )


def _load_background_from_json(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        "consensus_report": data.get("consensus_report") or data.get("final_report") or "",
        "assumption_report": data.get("assumption_report", ""),
        "final_report": data.get("final_report", ""),
    }


def _print_summary(result: dict) -> None:
    section_plans = result.get("subgraph_outputs", {}).get("section_planner", {}).get("section_plans", {})
    if not section_plans:
        section_plans = result.get("section_plans", {})
    ticker = result.get("ticker", "?")
    print(f"\n=== Section Planner Demo: {ticker} ===")
    print(f"Sections planned: {len(section_plans)}")
    for section_id, plan in section_plans.items():
        nodes = plan.get("nodes", [])
        level_1 = [n for n in nodes if int(n.get("level", 0)) == 1]
        flags = plan.get("data_quality_flags", [])
        print(f"\n--- {section_id}: {plan.get('section_title', section_id)} ---")
        print(f"Root: {plan.get('root_question', '')[:200]}")
        print(f"Sub-questions (L1): {len(level_1)} | Total nodes: {len(nodes)}")
        if flags:
            print(f"Flags: {', '.join(flags[:3])}")


def _run_single_section(
    deps: EquityResearchDeps,
    state: dict,
    section_id: str,
    *,
    enable_grounding: bool,
) -> dict:
    background = {
        "consensus_report": state.get("consensus_report", ""),
        "assumption_report": state.get("assumption_report", ""),
        "final_report": state.get("final_report") or "",
    }
    req = build_section_planner_request(
        state,
        section_id,
        background,
        enable_grounding=enable_grounding,
    )
    compiled = SectionPlannerSubgraph(deps).compile()
    subgraph_input = empty_section_planner_state(req)
    return compiled.invoke(subgraph_input)


def _run_all_sections(
    deps: EquityResearchDeps,
    state: dict,
    *,
    enable_grounding: bool,
) -> dict:
    planner = create_dynamic_planning(deps)
    working = dict(state)
    working["enable_planner_grounding"] = enable_grounding
    return planner(working)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run section question tree planner demo")
    parser.add_argument("ticker", help="Stock ticker, e.g. NVDA")
    parser.add_argument(
        "--section-id",
        default="4_industry_and_competition",
        help="Single section to plan (ignored with --all-sections)",
    )
    parser.add_argument("--sector", default="", help="Sector label")
    parser.add_argument("--user-focus", default="", help="Optional user focus for planner")
    parser.add_argument("--time-horizon", default="", help="Optional time horizon, e.g. FY26-FY27")
    parser.add_argument("--all-sections", action="store_true", help="Plan all MVP1 research sections")
    parser.add_argument(
        "--with-task-analysis",
        action="store_true",
        help="Run consensus + assumption subgraphs first for background",
    )
    parser.add_argument(
        "--background-json",
        help="Load consensus_report / assumption_report from a JSON file",
    )
    parser.add_argument(
        "--with-grounding",
        action="store_true",
        help="Enable lightweight web_search grounding in planner",
    )
    parser.add_argument("--output", "-o", help="Write JSON result to file")
    parser.add_argument("--json", action="store_true", help="Print full JSON to stdout")
    args = parser.parse_args(argv)

    config = DEFAULT_CONFIG.copy()
    deps = _build_deps(config)

    state = empty_equity_research_state()
    state.update({
        "ticker": args.ticker.upper(),
        "sector": args.sector,
        "user_focus": args.user_focus or None,
        "time_horizon": args.time_horizon or state.get("time_horizon"),
        "documents": [],
        "api_calls": 0,
    })

    task_analysis_output: dict = {}

    if args.background_json:
        bg = _load_background_from_json(Path(args.background_json))
        state["consensus_report"] = bg["consensus_report"]
        state["assumption_report"] = bg["assumption_report"]
        if bg["final_report"]:
            state["final_report"] = bg["final_report"]

    if args.with_task_analysis:
        logger.info("Running task analysis (consensus + assumption)...")
        analyze = create_analyze_research_task(deps)
        analyzed = analyze(state)
        state.update(analyzed)
        task_analysis_output = dict(analyzed.get("subgraph_outputs", {}))

    if args.all_sections:
        logger.info("Planning sections: %s", ", ".join(planner_section_ids()))
        planner_result = _run_all_sections(deps, state, enable_grounding=args.with_grounding)
        section_plans = planner_result.get("section_plans", {})
        exploration_graph = planner_result.get("planner_exploration_graph", {})
        api_calls = planner_result.get("api_calls", state.get("api_calls", 0))
        research_traces = planner_result.get("research_traces", [])
    else:
        logger.info("Planning section: %s", args.section_id)
        section_result = _run_single_section(
            deps,
            state,
            args.section_id,
            enable_grounding=args.with_grounding,
        )
        section_plans = {args.section_id: section_result.get("plan", {})}
        exploration_graph = section_result.get("exploration_graph", {})
        api_calls = int(section_result.get("api_calls", state.get("api_calls", 0)))
        research_traces = list(section_result.get("research_traces", []))

    result = {
        "ticker": state["ticker"],
        "sector": state.get("sector", ""),
        "section_plans": section_plans,
        "planner_exploration_graph": exploration_graph,
        "api_calls": api_calls,
        "research_traces": research_traces,
        "subgraph_outputs": {
            "section_planner": {
                "section_plans": section_plans,
                "exploration_graph": exploration_graph,
            },
        },
    }
    if task_analysis_output:
        result["subgraph_outputs"]["task_analysis"] = task_analysis_output
        result["consensus_report"] = state.get("consensus_report", "")
        result["assumption_report"] = state.get("assumption_report", "")

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        _print_summary(result)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        logger.info("Wrote %s", out_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
