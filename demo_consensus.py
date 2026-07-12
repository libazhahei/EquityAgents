#!/usr/bin/env python3
"""Manual CLI demo for the consensus research subgraph.

For the full parent spine (consensus → assumption → HR → planner → section
research) with durable checkpoints, see demo_equity_research.py.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from tradingagents.dataflows.config import set_config
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.runtime.demo_graph import ConsensusDemoGraph
from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.tasks.consensus.profile import CONSENSUS_TASK_PROFILE
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


def _print_summary(result: dict) -> None:
    view = result.get("structured_view") or result.get("consensus_view") or {}
    report = result.get("final_report") or result.get("consensus_report") or ""
    iterations = result.get("iterations") or result.get("consensus_iterations", 0)
    coverage = view.get("coverage_score", "n/a")
    print(f"\n=== Consensus Demo: {view.get('ticker', '?')} ===")
    print(f"Iterations: {iterations}")
    print(f"Coverage score: {coverage}")
    print(f"Report length: {len(report)} chars")
    if report:
        print("\n--- Report excerpt ---")
        print(report[:1200])
        if len(report) > 1200:
            print("...")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run consensus subgraph demo")
    parser.add_argument("ticker", help="Stock ticker, e.g. NVDA")
    parser.add_argument("--sector", default="", help="Sector label")
    parser.add_argument("--max-iterations", type=int, default=3, help="Max research loops")
    parser.add_argument("--output", "-o", help="Write JSON result to file")
    parser.add_argument("--json", action="store_true", help="Print full JSON to stdout")
    parser.add_argument(
        "--mode",
        choices=["demo-graph", "subgraph"],
        default="demo-graph",
        help="demo-graph: minimal 2-node graph; subgraph: direct GenericResearchSubgraph",
    )
    parser.add_argument(
        "--with-assumption",
        action="store_true",
        help="After consensus subgraph, run ASSUMPTION_TASK_PROFILE",
    )
    parser.add_argument(
        "--quick-research",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override equity_research.quick_research (default: config / env). "
        "When on, deep-tier planner calls use quick_llm.",
    )
    args = parser.parse_args(argv)

    config = DEFAULT_CONFIG.copy()
    if args.quick_research is not None:
        config.setdefault("equity_research", {})["quick_research"] = bool(args.quick_research)
    deps = _build_deps(config)
    logger.info(
        "quick_research=%s",
        config.get("equity_research", {}).get("quick_research"),
    )

    if not getattr(deps.perplexity, "api_key", None):
        logger.warning("PERPLEXITY_API_KEY not set — searches may fail")

    if args.mode == "subgraph":
        from tradingagents.equity_research.runtime.state import empty_agent_state
        from tradingagents.equity_research.state.consensus_schemas import empty_structured_consensus_view

        compiled = GenericResearchSubgraph(deps, CONSENSUS_TASK_PROFILE).compile()
        init = empty_agent_state(
            {"ticker": args.ticker.upper(), "sector": args.sector, "documents": [], "api_calls": 0},
            task_profile=CONSENSUS_TASK_PROFILE.to_dict(),
            max_iterations=args.max_iterations,
        )
        init["structured_view"] = empty_structured_consensus_view(args.ticker.upper()).model_dump()
        result = compiled.invoke(init)
        if args.with_assumption:
            from tradingagents.equity_research.agents.assumption.subgraph import _map_assumption_result, _seed_assumption_state
            # from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph
            from tradingagents.equity_research.tasks.assumption.profile import ASSUMPTION_TASK_PROFILE

            parent = {
                "ticker": args.ticker.upper(),
                "sector": args.sector,
                "consensus_view": result.get("structured_view", {}),
                "consensus_report": result.get("final_report", ""),
                "consensus_search_memory": result.get("search_memory", []),
                "consensus_evidence_buffer": result.get("evidence_buffer", []),
                "documents": result.get("documents", []),
                "api_calls": result.get("api_calls", 0),
            }
            assumption_compiled = GenericResearchSubgraph(deps, ASSUMPTION_TASK_PROFILE).compile()
            assumption_result = assumption_compiled.invoke(
                _seed_assumption_state(parent, ASSUMPTION_TASK_PROFILE),
            )
            mapped = _map_assumption_result(deps, parent, assumption_result, ASSUMPTION_TASK_PROFILE)
            result = {**result, **mapped}
    else:
        demo = ConsensusDemoGraph(
            deps,
            ticker=args.ticker.upper(),
            sector=args.sector,
            max_iterations=args.max_iterations,
        )
        result = demo.invoke()

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
