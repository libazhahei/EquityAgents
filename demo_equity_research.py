#!/usr/bin/env python3
"""End-to-end CLI for the equity research parent spine.

Runs: initialize → consensus → assumption → HR1 → planner → HR2 →
section research loop → END.

On completion, writes a run bundle (full state, progress events, research
traces, summary) similar to demo_consensus ``-o`` output — default under
``out/<TICKER>_equity_<timestamp>/``.

Visualize with:
  uv run python demo_equity_research.py NVDA --human-review-json examples/human_review_passthrough.json --output out/nvda_equity_e2e.json
  uv run python scripts/visualize_equity_research_trace.py out/.../full_state.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research.graph.checkpointer import list_run_tree
from tradingagents.equity_research.graph.equity_research_graph import EquityResearchGraph
from tradingagents.equity_research.runtime.progress import ProgressEvent, stdout_progress_sink

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _print_summary(state: dict) -> None:
    ticker = state.get("ticker", "?")
    print(f"\n=== Equity Research E2E: {ticker} ===")
    print(f"run_id: {state.get('run_id', '')}")
    cv = state.get("consensus_view") or {}
    print(f"Consensus coverage: {cv.get('coverage_score', 'n/a')}")
    av = state.get("assumption_view") or {}
    amap = av.get("assumption_map") or state.get("assumption_map") or []
    print(f"Assumption map items: {len(amap)}")
    plans = state.get("section_plans") or {}
    print(f"Section plans: {len(plans)}")
    selected = state.get("selected_section_ids") or []
    print(f"Selected sections: {selected}")
    outputs = state.get("section_research_outputs") or {}
    print(f"Section research outputs: {list(outputs.keys())}")
    for sid, out in outputs.items():
        text = out.get("final_section_text") or out.get("executive_summary") or ""
        print(f"\n--- {sid} excerpt ---")
        print(text[:800] + ("..." if len(text) > 800 else ""))


def _default_out_dir(ticker: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("out") / f"{ticker.upper()}_equity_{stamp}"


def _resolve_out_paths(output: str | None, ticker: str) -> tuple[Path, Path]:
    """Return (bundle_dir, full_state_path)."""
    if not output:
        bundle = _default_out_dir(ticker)
        return bundle, bundle / "full_state.json"

    path = Path(output)
    if path.suffix.lower() == ".json":
        return path.parent if str(path.parent) != "" else Path("."), path
    # Treat as directory
    return path, path / "full_state.json"


def _build_run_summary(
    state: dict[str, Any],
    *,
    progress_events: list[dict[str, Any]],
) -> dict[str, Any]:
    outputs = state.get("section_research_outputs") or {}
    plans = state.get("section_plans") or {}
    return {
        "ticker": state.get("ticker"),
        "run_id": state.get("run_id"),
        "trade_date": state.get("trade_date"),
        "report_id": state.get("report_id"),
        "selected_section_ids": state.get("selected_section_ids") or [],
        "section_plans_count": len(plans),
        "section_research_outputs": list(outputs.keys()),
        "consensus_coverage": (state.get("consensus_view") or {}).get("coverage_score"),
        "assumption_items": len(
            (state.get("assumption_view") or {}).get("assumption_map")
            or state.get("assumption_map")
            or []
        ),
        "research_traces_count": len(state.get("research_traces") or []),
        "progress_events_count": len(progress_events),
        "api_calls": state.get("api_calls", 0),
        "errors": state.get("errors") or [],
        "warnings": state.get("warnings") or [],
        "stages_seen": sorted({e.get("stage") for e in progress_events if e.get("stage")}),
    }


def save_run_bundle(
    state: dict[str, Any],
    *,
    bundle_dir: Path,
    full_state_path: Path,
    progress_events: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Path]:
    """Persist full state + companion trace/progress files. Returns written paths."""
    bundle_dir.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    full_state_path.parent.mkdir(parents=True, exist_ok=True)
    full_state_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    written["full_state"] = full_state_path

    # Companion files live next to full_state when -o is a .json file,
    # otherwise inside the bundle directory.
    if full_state_path.name == "full_state.json":
        base = bundle_dir
        stem_prefix = ""
    else:
        base = full_state_path.parent
        stem_prefix = full_state_path.stem + "."

    progress_path = base / f"{stem_prefix}progress_events.json"
    traces_path = base / f"{stem_prefix}research_traces.json"
    summary_path = base / f"{stem_prefix}run_summary.json"
    tree_path = base / f"{stem_prefix}run_tree.json"

    progress_path.write_text(json.dumps(progress_events, indent=2, default=str), encoding="utf-8")
    written["progress_events"] = progress_path

    traces = state.get("research_traces") or []
    traces_path.write_text(json.dumps(traces, indent=2, default=str), encoding="utf-8")
    written["research_traces"] = traces_path

    summary = _build_run_summary(state, progress_events=progress_events)
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    written["run_summary"] = summary_path

    run_id = str(state.get("run_id") or "")
    ticker = str(state.get("ticker") or "")
    try:
        cache_root = Path(
            config.get("data_cache_dir")
            or Path.home() / ".tradingagents" / "cache"
        )
        tree = list_run_tree(cache_root, ticker, run_id) if ticker and run_id else []
    except Exception as exc:
        logger.warning("Could not load run_tree: %s", exc)
        tree = []
    tree_path.write_text(json.dumps(tree, indent=2, default=str), encoding="utf-8")
    written["run_tree"] = tree_path

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run equity research end-to-end spine")
    parser.add_argument("ticker", help="Stock ticker, e.g. NVDA")
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        help="As-of / trade date YYYY-MM-DD",
    )
    parser.add_argument("--run-id", default=None, help="Stable run id (default: new UUID)")
    parser.add_argument(
        "--human-review-json",
        default=None,
        help="JSON file with human_review_1 / human_review_2 patches",
    )
    parser.add_argument(
        "--output",
        "-o",
        help=(
            "Output path: a .json file (full state + sibling *.progress_events.json etc.) "
            "or a directory (writes full_state.json + companions). "
            "Default: out/<TICKER>_equity_<timestamp>/"
        ),
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip writing the run bundle (stdout summary only)",
    )
    parser.add_argument("--json", action="store_true", help="Print full state JSON to stdout")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "--quick-research",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Override equity_research.quick_research (default: config / env). "
        "When on, consensus/assumption/section deep-tier calls use quick_llm.",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="After save, also write an HTML visualization next to the bundle",
    )
    args = parser.parse_args(argv)

    config = DEFAULT_CONFIG.copy()
    if args.quick_research is not None:
        config.setdefault("equity_research", {})["quick_research"] = bool(args.quick_research)
    graph = EquityResearchGraph(debug=args.debug, config=config, init_database=True)
    graph.subscribe_progress(stdout_progress_sink)

    logger.info(
        "Starting E2E equity research for %s on %s (run_id=%s, quick_research=%s)",
        args.ticker,
        args.date,
        args.run_id or "auto",
        config.get("equity_research", {}).get("quick_research"),
    )
    state, summary = graph.propagate(
        args.ticker,
        args.date,
        run_id=args.run_id,
        human_review=args.human_review_json,
        auto_resume_human=True,
    )
    state = state or {}

    progress_events = [e.to_dict() for e in graph.iter_progress()]

    if not args.no_save:
        bundle_dir, full_state_path = _resolve_out_paths(args.output, args.ticker)
        written = save_run_bundle(
            state,
            bundle_dir=bundle_dir,
            full_state_path=full_state_path,
            progress_events=progress_events,
            config=config,
        )
        for label, path in written.items():
            logger.info("Wrote %s → %s", label, path)

        if args.visualize:
            from scripts.visualize_equity_research_trace import render_html

            html_path = full_state_path.with_suffix(".html")
            if full_state_path.name == "full_state.json":
                html_path = bundle_dir / "trace.html"
            html_path.write_text(render_html(state, progress_events=progress_events), encoding="utf-8")
            logger.info("Wrote visualization → %s", html_path)

    if args.json:
        print(json.dumps(state, indent=2, default=str))
    else:
        _print_summary(state)
        if summary:
            print(f"\nSummary excerpt ({len(summary)} chars shown cap 500)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
