#!/usr/bin/env python3
"""Visualize section question tree planner output (demo_planner / dynamic_planning JSON)."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

_SECTION_ORDER = [
    "2_company_overview",
    "3_business_model",
    "4_industry_and_competition",
    "5_historical_financials",
    "6_earnings_forecast",
    "7_valuation",
    "8_scenario_and_sensitivity",
    "9_risks",
    "1_investment_summary",
    "10_appendix",
]


def _load_state(path: Path | None) -> dict[str, Any]:
    if path and path.name == "-":
        return json.load(sys.stdin)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("input path required")


def _section_plans(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if state.get("section_plans"):
        return dict(state["section_plans"])
    subgraph = state.get("subgraph_outputs", {}).get("section_planner", {})
    return dict(subgraph.get("section_plans") or {})


def _exploration_graph(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("planner_exploration_graph"):
        return state["planner_exploration_graph"]
    subgraph = state.get("subgraph_outputs", {}).get("section_planner", {})
    return dict(subgraph.get("exploration_graph") or {})


def _ordered_section_ids(plans: dict[str, dict[str, Any]]) -> list[str]:
    known = [sid for sid in _SECTION_ORDER if sid in plans]
    extra = [sid for sid in plans if sid not in known]
    return known + sorted(extra)


def _mermaid_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)


def _mermaid_label(text: str, *, max_len: int = 90) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned.replace('"', "'").replace("[", "(").replace("]", ")")


def _node_by_id(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {n.get("id", f"q{i}"): n for i, n in enumerate(plan.get("nodes") or [])}


def build_section_overview_mermaid(state: dict[str, Any]) -> str:
    plans = _section_plans(state)
    ticker = state.get("ticker", "?")
    if not plans:
        return "flowchart LR\n    empty[No section_plans]"

    lines = ["flowchart TB", f'    ROOT["{ticker}<br/>Section Plans"]']
    for section_id in _ordered_section_ids(plans):
        plan = plans[section_id]
        sid = _mermaid_id(section_id)
        nodes = plan.get("nodes") or []
        level_1 = sum(1 for n in nodes if int(n.get("level", 0)) == 1)
        flags = len(plan.get("data_quality_flags") or [])
        title = _mermaid_label(plan.get("section_title", section_id), max_len=40)
        label = f"{section_id}<br/>{title}<br/>{len(nodes)} nodes / L1={level_1}"
        if flags:
            label += f"<br/>flags={flags}"
        lines.append(f'    {sid}["{label}"]')
        lines.append(f"    ROOT --> {sid}")
    return "\n".join(lines)


def build_question_tree_mermaid(plan: dict[str, Any]) -> str:
    nodes = plan.get("nodes") or []
    if not nodes:
        return "flowchart LR\n    empty[No question nodes]"

    lines = ["flowchart TD"]
    by_id = _node_by_id(plan)
    for node in nodes:
        nid = _mermaid_id(node.get("id", ""))
        level = int(node.get("level", 0))
        qid = node.get("id", "")
        question = _mermaid_label(node.get("question", ""))
        prefix = "ROOT" if level == 0 else f"L{level}"
        agent = node.get("downstream_agent") or ""
        agent_hint = f"<br/>agent={agent}" if agent else ""
        lines.append(f'    {nid}["{prefix} {qid}<br/>{question}{agent_hint}"]')

    for node in nodes:
        parent_id = node.get("parent_id")
        if not parent_id:
            continue
        child_id = _mermaid_id(node.get("id", ""))
        parent_nid = _mermaid_id(parent_id)
        if parent_id in by_id:
            lines.append(f"    {parent_nid} --> {child_id}")
    return "\n".join(lines)


def build_execution_order_mermaid(plan: dict[str, Any]) -> str:
    order = plan.get("execution_order") or []
    by_id = _node_by_id(plan)
    if not order:
        return "flowchart LR\n    empty[No execution_order]"

    lines = ["flowchart LR"]
    prev: str | None = None
    for i, qid in enumerate(order):
        node = by_id.get(qid, {})
        nid = _mermaid_id(f"exec_{qid}")
        label = _mermaid_label(f"{i + 1}. {node.get('question', qid)}", max_len=70)
        lines.append(f'    {nid}["{label}"]')
        if prev:
            lines.append(f"    {prev} --> {nid}")
        prev = nid
    return "\n".join(lines)


def build_coverage_mermaid(plan: dict[str, Any]) -> str:
    coverage = plan.get("coverage_map") or {}
    if not coverage:
        return "flowchart LR\n    empty[No coverage_map]"

    lines = ["flowchart LR", f'    SEC["{plan.get("section_id", "section")}"]']
    by_id = _node_by_id(plan)
    for output, qids in coverage.items():
        out_id = _mermaid_id(f"out_{output}")
        out_label = _mermaid_label(output, max_len=50)
        lines.append(f'    {out_id}["{out_label}"]')
        lines.append(f"    SEC --> {out_id}")
        for qid in qids or []:
            q_nid = _mermaid_id(qid)
            if qid not in by_id:
                lines.append(f'    {q_nid}["{qid}"]')
            lines.append(f"    {out_id} --> {q_nid}")
    return "\n".join(lines)


def build_exploration_overview_mermaid(state: dict[str, Any]) -> str:
    graph = _exploration_graph(state)
    nodes = graph.get("nodes") or {}
    if not nodes:
        return "flowchart LR\n    empty[No planner_exploration_graph]"

    lines = ["flowchart TB", '    ROOT["Planner exploration branches"]']
    for nid, node in nodes.items():
        safe = _mermaid_id(nid)
        branch = _mermaid_label(node.get("branch_id", nid), max_len=50)
        cov = node.get("coverage_score", 0)
        route = node.get("routing_decision", "")
        qcount = len(node.get("query_plan") or [])
        label = f"{branch}<br/>questions={qcount}<br/>cov={cov}<br/>{route}"
        lines.append(f'    {safe}["{label}"]')
        lines.append(f"    ROOT --> {safe}")
    return "\n".join(lines)


def _summary_rows(state: dict[str, Any]) -> list[tuple[str, str]]:
    plans = _section_plans(state)
    total_nodes = sum(len(p.get("nodes") or []) for p in plans.values())
    total_flags = sum(len(p.get("data_quality_flags") or []) for p in plans.values())
    traces = state.get("research_traces") or []
    exploration = _exploration_graph(state)
    return [
        ("Ticker", str(state.get("ticker", "?"))),
        ("Sections planned", str(len(plans))),
        ("Total question nodes", str(total_nodes)),
        ("Data quality flags", str(total_flags)),
        ("API calls", str(state.get("api_calls", 0))),
        ("Exploration branches", str(len(exploration.get("nodes") or {}))),
        ("Research trace events", str(len(traces))),
        ("Has task_analysis", str(bool(state.get("subgraph_outputs", {}).get("task_analysis")))),
    ]


def _section_summary_rows(plan: dict[str, Any]) -> list[tuple[str, str]]:
    nodes = plan.get("nodes") or []
    level_1 = [n for n in nodes if int(n.get("level", 0)) == 1]
    return [
        ("Section", f"{plan.get('section_id', '')} — {plan.get('section_title', '')}"),
        ("Planning thesis", str(plan.get("planning_thesis", ""))[:500]),
        ("Root question", str(plan.get("root_question", ""))[:500]),
        ("Nodes", str(len(nodes))),
        ("Level-1 sub-questions", str(len(level_1))),
        ("Coverage outputs", str(len(plan.get("coverage_map") or {}))),
        ("Execution order length", str(len(plan.get("execution_order") or []))),
        ("Data quality flags", str(len(plan.get("data_quality_flags") or []))),
        ("Planner notes", str(plan.get("planner_notes") or "")),
    ]


def _trace_table_rows(state: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for t in state.get("research_traces") or []:
        payload = t.get("payload") or {}
        rows.append([
            t.get("node_name", ""),
            json.dumps(payload, ensure_ascii=False) if payload else "",
        ])
    return rows


def _flags_list(flags: list[str]) -> str:
    if not flags:
        return "<p><em>No data quality flags.</em></p>"
    items = "".join(f"<li>{html.escape(f)}</li>" for f in flags)
    return f"<ul>{items}</ul>"


def _render_section_block(section_id: str, plan: dict[str, Any]) -> str:
    title = html.escape(f"{section_id}: {plan.get('section_title', section_id)}")
    summary_html = "\n".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in _section_summary_rows(plan)
    )
    tree = build_question_tree_mermaid(plan)
    execution = build_execution_order_mermaid(plan)
    coverage = build_coverage_mermaid(plan)
    flags_html = _flags_list(plan.get("data_quality_flags") or [])

    nodes_table = ""
    for node in plan.get("nodes") or []:
        nodes_table += (
            "<tr>"
            f"<td><code>{html.escape(str(node.get('id', '')))}</code></td>"
            f"<td>{int(node.get('level', 0))}</td>"
            f"<td>{html.escape(str(node.get('question', '')))}</td>"
            f"<td>{html.escape(str(node.get('expected_output', '')))}</td>"
            f"<td>{html.escape(str(node.get('downstream_agent') or ''))}</td>"
            "</tr>\n"
        )

    return f"""
  <details class="section-block" open>
    <summary><h2 style="display:inline">{title}</h2></summary>
    <table>{summary_html}</table>
    <h3>Question tree</h3>
    <div class="mermaid">
{tree}
    </div>
    <h3>Execution order</h3>
    <div class="mermaid">
{execution}
    </div>
    <h3>Coverage map</h3>
    <div class="mermaid">
{coverage}
    </div>
    <h3>Data quality flags</h3>
    {flags_html}
    <h3>Nodes table</h3>
    <table>
      <tr><th>ID</th><th>Level</th><th>Question</th><th>Expected output</th><th>Agent</th></tr>
      {nodes_table}
    </table>
  </details>
"""


def render_html(
    state: dict[str, Any],
    *,
    title: str | None = None,
    section_filter: str | None = None,
) -> str:
    ticker = str(state.get("ticker", "Research"))
    page_title = title or f"{ticker} Section Planner Visualization"
    plans = _section_plans(state)
    section_ids = _ordered_section_ids(plans)
    if section_filter:
        section_ids = [sid for sid in section_ids if sid == section_filter]

    overview = build_section_overview_mermaid(state)
    exploration = build_exploration_overview_mermaid(state)

    summary_html = "\n".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in _summary_rows(state)
    )

    section_blocks = "".join(
        _render_section_block(sid, plans[sid])
        for sid in section_ids
        if sid in plans
    )

    trace_rows = ""
    for name, payload in _trace_table_rows(state):
        trace_rows += (
            f"<tr><td><code>{html.escape(name)}</code></td>"
            f"<td><pre>{html.escape(payload)}</pre></td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(page_title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 1400px; line-height: 1.5; }}
    h1, h2, h3 {{ margin-top: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.85rem; margin: 0; }}
    .mermaid {{ background: #fafafa; padding: 1rem; border-radius: 8px; overflow-x: auto; margin: 1rem 0; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; }}
    details.section-block {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 0.5rem 1rem 1rem; margin: 1.5rem 0; }}
    summary {{ cursor: pointer; padding: 0.5rem 0; }}
  </style>
</head>
<body>
  <h1>{html.escape(page_title)}</h1>
  <p>Section question tree planner output — question trees, coverage maps, and execution order.</p>

  <h2>Summary</h2>
  <table>{summary_html}</table>

  <h2>All sections overview</h2>
  <div class="mermaid">
{overview}
  </div>

  <h2>Planner exploration branches</h2>
  <div class="mermaid">
{exploration}
  </div>

  <h2>Per-section plans</h2>
  {section_blocks}

  <h2>Research traces</h2>
  <table>
    <tr><th>Node</th><th>Payload</th></tr>
    {trace_rows}
  </table>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
  </script>
</body>
</html>
"""


def render_markdown(
    state: dict[str, Any],
    *,
    section_filter: str | None = None,
) -> str:
    ticker = state.get("ticker", "Research")
    plans = _section_plans(state)
    section_ids = _ordered_section_ids(plans)
    if section_filter:
        section_ids = [sid for sid in section_ids if sid == section_filter]

    lines = [
        f"# {ticker} Section Planner Visualization",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
    ]
    for k, v in _summary_rows(state):
        lines.append(f"| {k} | {v} |")

    lines.extend([
        "",
        "## Sections overview",
        "",
        "```mermaid",
        build_section_overview_mermaid(state),
        "```",
        "",
        "## Exploration branches",
        "",
        "```mermaid",
        build_exploration_overview_mermaid(state),
        "```",
    ])

    for sid in section_ids:
        plan = plans.get(sid)
        if not plan:
            continue
        lines.extend([
            "",
            f"## {sid}: {plan.get('section_title', sid)}",
            "",
            f"**Root:** {plan.get('root_question', '')}",
            "",
            "### Question tree",
            "",
            "```mermaid",
            build_question_tree_mermaid(plan),
            "```",
            "",
            "### Execution order",
            "",
            "```mermaid",
            build_execution_order_mermaid(plan),
            "```",
        ])

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visualize section planner JSON output")
    parser.add_argument("input", type=Path, help="Path to planner JSON (use - for stdin)")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file (.html or .md); default: input stem + .html",
    )
    parser.add_argument(
        "--format",
        choices=["html", "md", "mermaid"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument("--title", help="Override page title")
    parser.add_argument(
        "--section-id",
        help="Render only one section (e.g. 4_industry_and_competition)",
    )
    parser.add_argument(
        "--diagram",
        choices=["overview", "exploration", "tree", "all"],
        default="all",
        help="For --format mermaid: which diagram to emit",
    )
    args = parser.parse_args(argv)

    state = _load_state(args.input)
    plans = _section_plans(state)
    if not plans:
        print("Warning: no section_plans found in input JSON", file=sys.stderr)

    if args.format == "html":
        content = render_html(state, title=args.title, section_filter=args.section_id)
        default_out = args.input.with_suffix(".html") if args.input.name != "-" else Path("planner_trace.html")
    elif args.format == "md":
        content = render_markdown(state, section_filter=args.section_id)
        default_out = args.input.with_suffix(".md") if args.input.name != "-" else Path("planner_trace.md")
    else:
        if args.diagram == "overview":
            content = build_section_overview_mermaid(state)
        elif args.diagram == "exploration":
            content = build_exploration_overview_mermaid(state)
        elif args.diagram == "tree" and args.section_id and args.section_id in plans:
            content = build_question_tree_mermaid(plans[args.section_id])
        else:
            parts = [
                build_section_overview_mermaid(state),
                build_exploration_overview_mermaid(state),
            ]
            if args.section_id and args.section_id in plans:
                parts.append(build_question_tree_mermaid(plans[args.section_id]))
            content = "\n\n".join(parts)
        default_out = args.input.with_suffix(".mmd") if args.input.name != "-" else Path("planner_trace.mmd")

    out_path = args.output or default_out
    if str(out_path) == "-":
        print(content)
    else:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(content, encoding="utf-8")
        print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
