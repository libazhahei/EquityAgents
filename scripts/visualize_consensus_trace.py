#!/usr/bin/env python3
"""Visualize consensus subgraph run from JSON output (e.g. out/nvda.json)."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

# Canonical process order for trace nodes (unknown nodes appended at end).
_TRACE_ORDER = [
    "consensus_skill_selector",
    "consensus_planner",
    "consensus_query_executor",
    "consensus_synthesizer",
    "consensus_coverage_reflector",
    "consensus_finalizer",
    "assumption_subgraph",
    "assumption_synthesizer",
    "assumption_query_executor",
    "consensus_human_review",
    "consensus_subgraph",
]


def _load_state(path: Path | None) -> dict[str, Any]:
    if path and path.name == "-":
        return json.load(sys.stdin)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("input path required")


def _view(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("structured_view") or state.get("consensus_view") or {}


def _iterations(state: dict[str, Any]) -> int:
    return int(state.get("iterations") or state.get("consensus_iterations") or 0)


def _max_iterations(state: dict[str, Any]) -> int:
    return int(state.get("max_iterations") or state.get("max_consensus_iterations") or 5)


def _trace_label(node_name: str, payload: dict[str, Any]) -> str:
    parts = [node_name.replace("_", " ")]
    if "skills" in payload:
        parts.append(f"skills={', '.join(payload['skills'])}")
    if "new_queries" in payload:
        parts.append(f"+{payload['new_queries']} queries")
    if "batch_size" in payload:
        dims = payload.get("dimensions") or []
        dim_hint = f" [{', '.join(dims[:3])}{'...' if len(dims) > 3 else ''}]" if dims else ""
        parts.append(f"batch={payload['batch_size']}{dim_hint}")
    if "overall_score" in payload:
        parts.append(f"score={payload['overall_score']}")
    if payload.get("routing"):
        parts.append(f"→ {payload['routing']}")
    if "report_chars" in payload:
        parts.append(f"{payload['report_chars']} chars")
    return "<br/>".join(html.escape(p) for p in parts)


def _mermaid_id(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)


def build_process_mermaid(state: dict[str, Any]) -> str:
    traces = state.get("research_traces") or []
    by_name = {t["node_name"]: t for t in traces if t.get("node_name")}
    ordered = [n for n in _TRACE_ORDER if n in by_name]
    ordered.extend(n for n in by_name if n not in ordered)

    coverage = state.get("coverage_report") or {}
    routing = coverage.get("routing_decision", "exit")
    score = coverage.get("overall_score", _view(state).get("coverage_score", ""))

    lines = ["flowchart TD"]
    prev: str | None = None
    for name in ordered:
        nid = _mermaid_id(name)
        payload = by_name[name].get("payload") or {}
        label = _trace_label(name, payload).replace('"', "'")
        lines.append(f'    {nid}["{label}"]')
        if prev:
            lines.append(f"    {prev} --> {nid}")
        prev = nid

    if "consensus_coverage_reflector" in by_name:
        ref_id = _mermaid_id("consensus_coverage_reflector")
        lines.append(f'    REF_NOTE["coverage {score} → {routing}"]')
        lines.append(f"    {ref_id} -.-> REF_NOTE")

    return "\n".join(lines)


def build_evidence_mermaid(state: dict[str, Any]) -> str:
    memory = state.get("search_memory") or []
    if not memory:
        return "flowchart LR\n    empty[No search_memory]"

    lines = ["flowchart TB"]
    by_iter: dict[int, list[dict]] = {}
    for rec in memory:
        it = int(rec.get("iteration", 0))
        by_iter.setdefault(it, []).append(rec)

    for it in sorted(by_iter):
        group_id = f"iter_{it}"
        label = f"Iteration {it}" if it else "Initial round"
        lines.append(f'    subgraph {group_id} ["{label}"]')
        for i, rec in enumerate(by_iter[it]):
            dim = rec.get("target_dimension", "?")
            q = str(rec.get("query", ""))[:60].replace('"', "'")
            node_id = f"{group_id}_q{i}"
            lines.append(f'        {node_id}["{dim}<br/>{q}..."]')
        lines.append("    end")

    return "\n".join(lines)


def build_results_mermaid(state: dict[str, Any]) -> str:
    coverage = state.get("coverage_report") or {}
    dim_scores = coverage.get("dimension_scores") or _view(state).get("dimension_coverage") or {}
    overall = coverage.get("overall_score", _view(state).get("coverage_score", 0))

    lines = [
        "flowchart TB",
        f'    ROOT["{_view(state).get("ticker", "?")} consensus<br/>score {overall}"]',
    ]
    for dim, status in dim_scores.items():
        did = _mermaid_id(dim)
        status_str = status.value if hasattr(status, "value") else str(status)
        lines.append(f'    {did}["{dim}<br/>{status_str}"]')
        lines.append(f"    ROOT --> {did}")

    return "\n".join(lines)


def build_exploration_mermaid(state: dict[str, Any]) -> str:
    graph = state.get("exploration_graph") or {}
    nodes = graph.get("nodes") or {}
    if not nodes:
        return "flowchart LR\n    empty[No exploration_graph nodes]"

    lines = ["flowchart LR"]
    for nid, node in nodes.items():
        safe = _mermaid_id(nid)
        it = node.get("iteration", 0)
        cov = node.get("coverage_score", 0)
        route = node.get("routing_decision", "")
        label = f"{nid}<br/>iter {it}<br/>cov {cov}<br/>{route}".replace('"', "'")
        lines.append(f'    {safe}["{label}"]')
        parent = node.get("parent_id")
        if parent and parent in nodes:
            lines.append(f"    {_mermaid_id(parent)} --> {safe}")

    return "\n".join(lines)


def _summary_rows(state: dict[str, Any]) -> list[tuple[str, str]]:
    view = _view(state)
    report = state.get("final_report") or state.get("consensus_report") or ""
    assumptions = state.get("assumptions") or state.get("consensus_assumptions") or {}
    skills = state.get("active_skills") or state.get("loaded_skills") or []

    rows = [
        ("Ticker", str(state.get("ticker", view.get("ticker", "?")))),
        ("Iterations", f"{_iterations(state)} / {_max_iterations(state)}"),
        ("API calls", str(state.get("api_calls", 0))),
        ("Documents", str(len(state.get("documents") or []))),
        ("Search records", str(len(state.get("search_memory") or []))),
        ("Coverage score", str((state.get("coverage_report") or {}).get("overall_score", view.get("coverage_score", "")))),
        ("Routing", str((state.get("coverage_report") or {}).get("routing_decision", ""))),
        ("Skills", ", ".join(skills) if skills else "(none)"),
        ("Report length", f"{len(report)} chars"),
        ("Assumption fields", str(len(assumptions)) if isinstance(assumptions, dict) else "0"),
        ("Compliance flags", str(len(state.get("compliance_flags") or []))),
        ("Errors", str(len(state.get("errors") or []))),
    ]
    return rows


def _trace_table_rows(state: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for t in state.get("research_traces") or []:
        payload = t.get("payload") or {}
        rows.append([
            t.get("node_name", ""),
            json.dumps(payload, ensure_ascii=False) if payload else "",
        ])
    return rows


def _search_table_rows(state: dict[str, Any], *, limit: int = 20) -> list[list[str]]:
    rows: list[list[str]] = []
    for rec in (state.get("search_memory") or [])[:limit]:
        summary = rec.get("answer_summary") or rec.get("answer", "")
        if len(summary) > 200:
            summary = summary[:200] + "..."
        rows.append([
            str(rec.get("iteration", 0)),
            rec.get("target_dimension", ""),
            rec.get("mode", ""),
            str(rec.get("query", ""))[:80],
            summary,
            str(len(rec.get("citations") or [])),
        ])
    return rows


def render_html(state: dict[str, Any], *, title: str | None = None) -> str:
    ticker = state.get("ticker") or _view(state).get("ticker", "Consensus")
    page_title = title or f"{ticker} Consensus Research Trace"

    process = build_process_mermaid(state)
    evidence = build_evidence_mermaid(state)
    results = build_results_mermaid(state)
    exploration = build_exploration_mermaid(state)

    summary_html = "\n".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in _summary_rows(state)
    )

    trace_rows = ""
    for name, payload in _trace_table_rows(state):
        trace_rows += (
            f"<tr><td><code>{html.escape(name)}</code></td>"
            f"<td><pre>{html.escape(payload)}</pre></td></tr>\n"
        )

    search_rows = ""
    for row in _search_table_rows(state):
        search_rows += "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>\n"

    assumptions = state.get("assumptions") or state.get("consensus_assumptions") or {}
    assumptions_pre = html.escape(json.dumps(assumptions, indent=2, ensure_ascii=False)[:8000])

    report = state.get("final_report") or state.get("consensus_report") or ""
    report_pre = html.escape(report[:12000])
    if len(report) > 12000:
        report_pre += "\n\n... (truncated)"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(page_title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 1200px; line-height: 1.5; }}
    h1, h2 {{ margin-top: 2rem; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
    th, td {{ border: 1px solid #ddd; padding: 0.5rem 0.75rem; text-align: left; vertical-align: top; }}
    th {{ background: #f5f5f5; }}
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.85rem; margin: 0; }}
    .mermaid {{ background: #fafafa; padding: 1rem; border-radius: 8px; overflow-x: auto; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>{html.escape(page_title)}</h1>
  <p>Generated from consensus subgraph JSON state.</p>

  <h2>Summary</h2>
  <table>{summary_html}</table>

  <h2>Process flow (research_traces)</h2>
  <div class="mermaid">
{process}
  </div>

  <h2>Evidence by iteration (search_memory)</h2>
  <div class="mermaid">
{evidence}
  </div>

  <h2>Dimension coverage</h2>
  <div class="mermaid">
{results}
  </div>

  <h2>Exploration graph</h2>
  <div class="mermaid">
{exploration}
  </div>

  <h2>Trace payload table</h2>
  <table>
    <tr><th>Node</th><th>Payload</th></tr>
    {trace_rows}
  </table>

  <h2>Search memory</h2>
  <table>
    <tr><th>Iter</th><th>Dimension</th><th>Mode</th><th>Query</th><th>Summary</th><th>Citations</th></tr>
    {search_rows}
  </table>

  <h2>Assumptions</h2>
  <pre>{assumptions_pre}</pre>

  <h2>Report excerpt</h2>
  <pre>{report_pre}</pre>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
  </script>
</body>
</html>
"""


def render_markdown(state: dict[str, Any]) -> str:
    ticker = state.get("ticker") or _view(state).get("ticker", "Consensus")
    lines = [
        f"# {ticker} Consensus Research Trace",
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
        "## Process flow",
        "",
        "```mermaid",
        build_process_mermaid(state),
        "```",
        "",
        "## Evidence",
        "",
        "```mermaid",
        build_evidence_mermaid(state),
        "```",
        "",
        "## Results",
        "",
        "```mermaid",
        build_results_mermaid(state),
        "```",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visualize consensus subgraph JSON output")
    parser.add_argument("input", type=Path, help="Path to JSON state (use - for stdin)")
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file (.html or .md); default: stdout for md, input stem .html",
    )
    parser.add_argument(
        "--format",
        choices=["html", "md", "mermaid"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument(
        "--diagram",
        choices=["process", "evidence", "results", "exploration", "all"],
        default="all",
        help="For --format mermaid: which diagram to emit",
    )
    args = parser.parse_args(argv)

    state = _load_state(args.input)

    if args.format == "html":
        content = render_html(state)
        out = args.output or args.input.with_suffix(".html")
        out.write_text(content, encoding="utf-8")
        print(f"Wrote {out}")
    elif args.format == "md":
        content = render_markdown(state)
        out = args.output
        if out:
            out.write_text(content, encoding="utf-8")
            print(f"Wrote {out}")
        else:
            print(content)
    else:
        builders = {
            "process": build_process_mermaid,
            "evidence": build_evidence_mermaid,
            "results": build_results_mermaid,
            "exploration": build_exploration_mermaid,
        }
        if args.diagram == "all":
            parts = [f"%% {name}\n{fn(state)}" for name, fn in builders.items()]
            content = "\n\n".join(parts)
        else:
            content = builders[args.diagram](state)
        out = args.output
        if out:
            out.write_text(content, encoding="utf-8")
            print(f"Wrote {out}")
        else:
            print(content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
