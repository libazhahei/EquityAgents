#!/usr/bin/env python3
"""Manual CLI for section research subgraph.

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
from tradingagents.equity_research.agents.research_loop.subgraph import create_run_section_research_subgraph
from tradingagents.equity_research.agents.task_analysis import create_analyze_research_task
from tradingagents.equity_research.runtime.section_research_subgraph import SectionResearchSubgraph
from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state
from tradingagents.equity_research.tasks.section_research.profile import SECTION_RESEARCH_TASK_PROFILE
from tradingagents.equity_research.tasks.section_research.seed import seed_section_research_state
from tradingagents.equity_research.templates.report_template import MVP1_REPORT_TEMPLATE
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
    nano_client = create_llm_client(
        provider=config["llm_provider"],
        model=config.get("nano_think_llm", "gpt-5.4-nano"),
        base_url=config.get("backend_url"),
        **llm_kwargs,
    )
    return EquityResearchDeps(
        config=config,
        deep_llm=deep_client.get_llm(),
        quick_llm=quick_client.get_llm(),
        nano_llm=nano_client.get_llm(),
    )


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_background_json(path: Path) -> dict:
    """Load consensus + assumption context from demo_consensus-style JSON (e.g. out/nvda5.json).

    Consensus view is stored as ``structured_view``; assumption as ``assumption_view``.
    """
    data = _load_json(path)
    consensus_view = (
        data.get("consensus_view")
        or data.get("structured_view")
        or {}
    )
    assumption_view = data.get("assumption_view") or {}
    assumption_report = data.get("assumption_report") or ""
    updates: dict = {
        "consensus_view": consensus_view,
        "assumption_view": assumption_view,
        "assumption_report": assumption_report,
    }
    if isinstance(consensus_view, dict) and consensus_view.get("ticker"):
        updates["ticker"] = str(consensus_view["ticker"]).upper()
    elif data.get("ticker"):
        updates["ticker"] = str(data["ticker"]).upper()
    if data.get("sector") is not None:
        updates["sector"] = data.get("sector", "")
    if data.get("documents"):
        updates["documents"] = data["documents"]
    if data.get("api_calls") is not None:
        updates["api_calls"] = int(data["api_calls"])
    return updates


def _load_planner_json(path: Path) -> dict:
    data = _load_json(path)
    updates: dict = {
        "section_plans": data.get("section_plans", data),
    }
    if data.get("ticker"):
        updates["ticker"] = str(data["ticker"]).upper()
    if data.get("sector") is not None:
        updates["sector"] = data.get("sector", "")
    return updates


def _print_summary(result: dict) -> None:
    section_id = result.get("section_id", "?")
    output = result.get("section_research_output") or {}
    plan = result.get("research_plan") or {}
    todo = result.get("research_todo_list") or {}
    print(f"\n=== Section Research: {result.get('ticker', '?')} / {section_id} ===")
    print(f"Report length: {len(output.get('final_section_text', '') or result.get('final_report', ''))} chars")
    print(f"Tasks: {len(plan.get('tasks', []))}")
    print(f"Todo items: {len(todo.get('items', []))}")
    print(f"Answer cards: {len(result.get('answer_cards') or {})}")
    coverage = result.get("coverage_report") or {}
    print(f"Coverage score: {coverage.get('overall_score', 'n/a')}")
    print(f"Next action: {coverage.get('recommended_next_action', 'n/a')}")

    # --- ParameterPreservingReducer summary ---
    registry = (
        output.get("parameter_registry")
        or result.get("parameter_registry")
        or {}
    )
    params = registry.get("parameters") or {}
    if params:
        conflicts = sum(1 for p in params.values() if p.get("is_conflict"))
        dims = registry.get("dimensions") or []
        print(f"Parameters: {len(params)} extracted, {conflicts} conflicts, {len(dims)} dimensions")
        # Show top 10 parameters by confidence (descending)
        sorted_params = sorted(
            params.items(),
            key=lambda kv: -(kv[1].get("current", {}).get("confidence", 0)),
        )
        for key, param in sorted_params[:10]:
            cur = param.get("current") or {}
            val = cur.get("value", "?")
            unit = cur.get("unit", "")
            as_of = cur.get("as_of", "?")
            conflict_mark = " ⚠️" if param.get("is_conflict") else ""
            print(f"  • {key}: {val}{unit} (as of: {as_of}){conflict_mark}")
        if len(params) > 10:
            print(f"  … and {len(params) - 10} more parameters")
    else:
        print("Parameters: none extracted (no evidence or skill context)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run section research subgraph",
        epilog=(
            "Example (no task_analysis):\n"
            "  uv run python demo_section_research.py NVDA \\\n"
            "    --background-json out/nvda5.json \\\n"
            "    --planner-json out/nvda_planner.json \\\n"
            "    --section-id 3_business_model -o out/nvda_section.json"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("ticker", nargs="?", default="", help="Stock ticker (optional if JSON has ticker)")
    parser.add_argument("--section-id", default="3_business_model", help="Report section id")
    parser.add_argument("--sector", default="", help="Sector label")
    parser.add_argument(
        "--planner-json",
        help="Section planner output (e.g. out/nvda_planner.json) with section_plans",
    )
    parser.add_argument(
        "--background-json",
        help="Consensus+assumption JSON (e.g. out/nvda5.json): structured_view, assumption_view",
    )
    parser.add_argument(
        "--views-json",
        help="Alias for --background-json",
    )
    parser.add_argument(
        "--with-task-analysis",
        action="store_true",
        help="Run consensus + assumption subgraphs live (optional; prefer --background-json)",
    )
    parser.add_argument("--max-iterations", type=int, default=5, help="Max PER iterations")
    parser.add_argument(
        "--max-sub-questions", type=int, default=None,
        help="Limit research to at most N sub-questions (truncates section plan nodes)",
    )
    parser.add_argument("--output", "-o", help="Write JSON result to file")
    parser.add_argument("--json", action="store_true", help="Print full JSON to stdout")
    parser.add_argument(
        "--mode",
        choices=["wrapper", "subgraph"],
        default="wrapper",
        help="wrapper: seed+map; subgraph: direct invoke",
    )
    parser.add_argument(
        "--quick-research",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override equity_research.quick_research (default: config / env). "
        "When on, deep-tier calls use quick_llm.",
    )
    parser.add_argument(
        "--skip-verify",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override equity_research.skip_verify (default: config / env). "
        "When on, verify steps are marked skipped without LLM/tool calls.",
    )
    args = parser.parse_args(argv)

    config = DEFAULT_CONFIG.copy()
    if args.quick_research is not None:
        config.setdefault("equity_research", {})["quick_research"] = bool(args.quick_research)
    if args.skip_verify is not None:
        config.setdefault("equity_research", {})["skip_verify"] = bool(args.skip_verify)
    deps = _build_deps(config)
    logger.info(
        "quick_research=%s skip_verify=%s",
        config.get("equity_research", {}).get("quick_research"),
        config.get("equity_research", {}).get("skip_verify"),
    )

    state = empty_equity_research_state()
    state.update({
        "ticker": args.ticker.upper() if args.ticker else "",
        "sector": args.sector,
        "documents": [],
        "api_calls": 0,
        "max_section_research_iterations": args.max_iterations,
        "max_research_iterations": args.max_iterations,
        "active_section_id": args.section_id,
    })

    background_path = args.background_json or args.views_json
    if background_path:
        bg = _load_background_json(Path(background_path))
        state.update(bg)
        logger.info(
            "Loaded background from %s (consensus_view=%s, assumption_view=%s)",
            background_path,
            "yes" if bg.get("consensus_view") else "no",
            "yes" if bg.get("assumption_view") else "no",
        )

    if args.planner_json:
        planner_updates = _load_planner_json(Path(args.planner_json))
        state.update(planner_updates)
        logger.info(
            "Loaded planner from %s (%d sections)",
            args.planner_json,
            len(state.get("section_plans") or {}),
        )

    if not state.get("ticker"):
        parser.error("ticker is required (positional arg or in --background-json / --planner-json)")

    if args.with_task_analysis:
        logger.info("Running task analysis (consensus + assumption)...")
        analyzed = create_analyze_research_task(deps)(state)
        state.update(analyzed)
    elif not background_path:
        logger.warning(
            "No --background-json provided; section research will run without consensus/assumption views. "
            "Use out/nvda5.json (structured_view + assumption_view) or --with-task-analysis.",
        )

    section_plan = (state.get("section_plans") or {}).get(args.section_id, {})
    if not section_plan:
        template = MVP1_REPORT_TEMPLATE.get(args.section_id, {})
        section_plan = {
            "section_id": args.section_id,
            "section_title": template.get("title", args.section_id),
            "root_question": f"What should the {args.section_id} section cover for {state['ticker']}?",
            "planning_thesis": template.get("intent_hint", ""),
            "nodes": [],
        }
        state.setdefault("section_plans", {})[args.section_id] = section_plan

    # Truncate sub-questions if --max-sub-questions is set
    if args.max_sub_questions is not None:
        all_nodes = section_plan.get("nodes") or []
        total_q = len(all_nodes)
        if total_q > args.max_sub_questions:
            section_plan["nodes"] = all_nodes[: args.max_sub_questions]
            state.setdefault("section_plans", {})[args.section_id] = section_plan
            logger.info(
                "Truncated sub-questions: %d → %d (out of %d total)",
                total_q, args.max_sub_questions, total_q,
            )
        else:
            logger.info(
                "Sub-questions: %d (≤ %d limit, no truncation)",
                total_q, args.max_sub_questions,
            )

    if args.mode == "subgraph":
        compiled = SectionResearchSubgraph(deps, SECTION_RESEARCH_TASK_PROFILE).compile()
        subgraph_input = seed_section_research_state(
            state, SECTION_RESEARCH_TASK_PROFILE,
            section_id=args.section_id,
            section_plan=section_plan,
        )
        subgraph_input["max_iterations"] = args.max_iterations
        raw = compiled.invoke(subgraph_input)
        from tradingagents.equity_research.agents.research_loop.subgraph import _map_section_research_result
        mapped = _map_section_research_result(
            deps, state, raw, SECTION_RESEARCH_TASK_PROFILE, section_id=args.section_id,
        )
        section_out = (mapped.get("section_research_outputs") or {}).get(args.section_id) or {}
        result = {
            "ticker": state["ticker"],
            "section_id": args.section_id,
            **mapped,
            "section_research_output": section_out,
            # Surface ParameterPreservingReducer data at top level for easy access
            "parameter_registry": section_out.get("parameter_registry") or mapped.get("parameter_registry") or {},
            "parameter_grid": section_out.get("parameter_grid") or mapped.get("parameter_grid") or "",
        }
    else:
        run = create_run_section_research_subgraph(deps)
        mapped = run(state)
        section_out = (mapped.get("section_research_outputs") or {}).get(args.section_id) or {}
        result = {
            "ticker": state["ticker"],
            "section_id": args.section_id,
            **mapped,
            "section_research_output": section_out,
            # Surface ParameterPreservingReducer data at top level for easy access
            "parameter_registry": section_out.get("parameter_registry") or mapped.get("parameter_registry") or {},
            "parameter_grid": section_out.get("parameter_grid") or mapped.get("parameter_grid") or "",
        }

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
