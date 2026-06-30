#!/usr/bin/env python3
"""Visualize consensus + assumption research trace from JSON output."""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Any

_CONSENSUS_TRACE_ORDER = [
    "consensus_skill_selector",
    "consensus_planner",
    "consensus_query_executor",
    "consensus_synthesizer",
    "consensus_coverage_reflector",
    "consensus_query_planner",
    "consensus_finalizer",
    "consensus_human_review",
    "consensus_subgraph",
]

_ASSUMPTION_TRACE_ORDER = [
    "assumption_skill_selector",
    "assumption_planner",
    "assumption_query_executor",
    "assumption_synthesizer",
    "assumption_coverage_reflector",
    "assumption_query_planner",
    "assumption_finalizer",
    "assumption_subgraph",
]

_TRACE_ORDER = _CONSENSUS_TRACE_ORDER + _ASSUMPTION_TRACE_ORDER


def _load_state(path: Path | None) -> dict[str, Any]:
    if path and path.name == "-":
        return json.load(sys.stdin)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("input path required")


def _consensus_view(state: dict[str, Any]) -> dict[str, Any]:
    if state.get("assumption_view") and not state.get("consensus_view"):
        parent = state.get("parent_context") or {}
        if parent.get("consensus_view"):
            return parent["consensus_view"]
    return state.get("consensus_view") or state.get("structured_view") or {}


def _assumption_view(state: dict[str, Any]) -> dict[str, Any]:
    return state.get("assumption_view") or {}


def _assumption_map(state: dict[str, Any]) -> list[dict[str, Any]]:
    if state.get("assumption_map"):
        return list(state["assumption_map"])
    view = _assumption_view(state)
    if view.get("assumption_map"):
        return list(view["assumption_map"])
    legacy = state.get("assumptions") or state.get("consensus_assumptions") or {}
    if isinstance(legacy, dict) and legacy:
        items = []
        for key, value in legacy.items():
            if key in {"top_research_priorities", "assumption_count"}:
                continue
            if isinstance(value, str):
                items.append({"id": key, "statement": value, "_legacy": True})
        return items
    return []


def _conflicts(state: dict[str, Any]) -> list[dict[str, Any]]:
    conflicts: list[dict] = []
    cv = _consensus_view(state)
    av = _assumption_view(state)
    if isinstance(cv.get("conflicts"), list):
        conflicts.extend(cv["conflicts"])
    if isinstance(av.get("conflicts"), list):
        conflicts.extend(av["conflicts"])
    return conflicts


def _detect_phases(state: dict[str, Any]) -> set[str]:
    phases = {"consensus"}
    traces = {t.get("node_name", "") for t in state.get("research_traces") or []}
    if (
        state.get("assumption_view")
        or state.get("assumption_report")
        or state.get("assumption_map")
        or any(n.startswith("assumption_") for n in traces)
    ):
        phases.add("assumption")
    return phases


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
    if "assumption_items" in payload:
        parts.append(f"assumptions={payload['assumption_items']}")
    return "<br/>".join(html.escape(p) for p in parts)


def _mermaid_id(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in text)


def build_process_mermaid(state: dict[str, Any], *, phase: str = "all") -> str:
    traces = state.get("research_traces") or []
    by_name = {t["node_name"]: t for t in traces if t.get("node_name")}
    order = []
    if phase in ("all", "consensus"):
        order.extend(_CONSENSUS_TRACE_ORDER)
    if phase in ("all", "assumption"):
        order.extend(_ASSUMPTION_TRACE_ORDER)
    ordered = [n for n in order if n in by_name]
    ordered.extend(n for n in by_name if n not in ordered)

    coverage = state.get("coverage_report") or {}
    routing = coverage.get("routing_decision", "exit")
    score = coverage.get("overall_score", _consensus_view(state).get("coverage_score", ""))

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


def build_evidence_mermaid(state: dict[str, Any], *, memory_key: str = "search_memory") -> str:
    memory = state.get(memory_key) or state.get("consensus_search_memory") or state.get("assumption_search_memory") or []
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
    view = _consensus_view(state)
    dim_scores = coverage.get("dimension_scores") or view.get("dimension_coverage") or {}
    overall = coverage.get("overall_score", view.get("coverage_score", 0))

    lines = [
        "flowchart TB",
        f'    ROOT["{view.get("ticker", "?")} consensus<br/>score {overall}"]',
    ]
    for dim, status in dim_scores.items():
        did = _mermaid_id(dim)
        status_str = status.value if hasattr(status, "value") else str(status)
        lines.append(f'    {did}["{dim}<br/>{status_str}"]')
        lines.append(f"    ROOT --> {did}")

    return "\n".join(lines)


def build_assumption_quality_mermaid(state: dict[str, Any]) -> str:
    view = _assumption_view(state)
    dim_scores = view.get("dimension_coverage") or {}
    overall = view.get("coverage_score", 0)
    ticker = view.get("ticker", state.get("ticker", "?"))

    lines = ["flowchart TB", f'    ROOT["{ticker} assumption quality<br/>score {overall}"]']
    if not dim_scores:
        lines.append('    empty[No quality dimensions scored]')
        lines.append("    ROOT --> empty")
        return "\n".join(lines)
    for dim, status in dim_scores.items():
        did = _mermaid_id(f"aq_{dim}")
        status_str = status.value if hasattr(status, "value") else str(status)
        lines.append(f'    {did}["{dim}<br/>{status_str}"]')
        lines.append(f"    ROOT --> {did}")
    return "\n".join(lines)


def build_assumption_map_mermaid(state: dict[str, Any]) -> str:
    items = _assumption_map(state)
    if not items:
        return "flowchart LR\n    empty[No assumption_map]"

    lines = ["flowchart TB", '    ROOT["Assumption map"]']
    for i, item in enumerate(items[:12]):
        nid = _mermaid_id(f"a_{item.get('id', i)}")
        stmt = str(item.get("statement", ""))[:80].replace('"', "'")
        cat = item.get("category", "")
        controversy = item.get("controversy_level", "")
        label = f"{item.get('id', f'A{i+1}')}<br/>{cat}<br/>{stmt}"
        if controversy:
            label += f"<br/>controversy={controversy}"
        lines.append(f'    {nid}["{label}"]')
        lines.append(f"    ROOT --> {nid}")
    return "\n".join(lines)


def build_conflicts_mermaid(state: dict[str, Any]) -> str:
    conflicts = _conflicts(state)
    if not conflicts:
        return "flowchart LR\n    empty[No conflicts recorded]"

    lines = ["flowchart TB", '    ROOT["Conflicts"]']
    for i, conflict in enumerate(conflicts[:10]):
        nid = _mermaid_id(f"conf_{i}")
        a = str(conflict.get("claim_a", ""))[:50].replace('"', "'")
        b = str(conflict.get("claim_b", ""))[:50].replace('"', "'")
        lines.append(f'    {nid}["{a}<br/>vs<br/>{b}"]')
        lines.append(f"    ROOT --> {nid}")
    return "\n".join(lines)


def build_priorities_mermaid(state: dict[str, Any]) -> str:
    view = _assumption_view(state)
    priorities = view.get("top_research_priorities") or state.get("research_directions") or []
    suggestions = view.get("research_suggestions") or state.get("research_suggestions") or []
    if not priorities and not suggestions:
        return "flowchart LR\n    empty[No research priorities]"

    lines = ["flowchart TB", '    ROOT["Research priorities"]']
    for i, p in enumerate(priorities[:8]):
        nid = _mermaid_id(f"p_{i}")
        lines.append(f'    {nid}["{str(p)[:70].replace(chr(34), chr(39))}"]')
        lines.append(f"    ROOT --> {nid}")
    for i, s in enumerate(suggestions[:5]):
        nid = _mermaid_id(f"s_{i}")
        direction = s.get("direction", str(s)) if isinstance(s, dict) else str(s)
        lines.append(f'    {nid}["suggestion: {direction[:60].replace(chr(34), chr(39))}"]')
        lines.append(f"    ROOT --> {nid}")
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
    view = _consensus_view(state)
    assumption_items = _assumption_map(state)
    falsification_count = sum(1 for item in assumption_items if item.get("falsification_tests"))
    report = state.get("final_report") or state.get("consensus_report") or ""
    assumption_report = state.get("assumption_report") or ""
    skills = state.get("active_skills") or state.get("loaded_skills") or []
    av = _assumption_view(state)
    priorities = av.get("top_research_priorities") or state.get("research_directions") or []

    rows = [
        ("Ticker", str(state.get("ticker", view.get("ticker", "?")))),
        ("Phases", ", ".join(sorted(_detect_phases(state)))),
        ("Iterations", f"{_iterations(state)} / {_max_iterations(state)}"),
        ("API calls", str(state.get("api_calls", 0))),
        ("Documents", str(len(state.get("documents") or []))),
        ("Search records", str(len(state.get("search_memory") or state.get("consensus_search_memory") or []))),
        ("Coverage score", str((state.get("coverage_report") or {}).get("overall_score", view.get("coverage_score", "")))),
        ("Routing", str((state.get("coverage_report") or {}).get("routing_decision", ""))),
        ("Skills", ", ".join(skills) if skills else "(none)"),
        ("Consensus report length", f"{len(report)} chars"),
        ("Assumption items", str(len(assumption_items))),
        ("Falsification tests", str(falsification_count)),
        ("Conflicts", str(len(_conflicts(state)))),
        ("Research priorities", str(len(priorities))),
        ("Assumption report length", f"{len(assumption_report)} chars"),
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
    memory = (
        state.get("search_memory")
        or state.get("consensus_search_memory")
        or state.get("assumption_search_memory")
        or []
    )
    for rec in memory[:limit]:
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


def _assumption_table_rows(state: dict[str, Any]) -> list[list[str]]:
    rows: list[list[str]] = []
    for item in _assumption_map(state):
        fals = item.get("falsification_tests") or []
        rows.append([
            str(item.get("id", "")),
            str(item.get("category", "")),
            str(item.get("statement", ""))[:200],
            str(item.get("consensus_anchor", ""))[:120],
            str(item.get("controversy_level", "")),
            "; ".join(str(x) for x in fals[:2])[:160],
            "(legacy)" if item.get("_legacy") else "",
        ])
    return rows


def render_html(state: dict[str, Any], *, title: str | None = None, phase: str = "all") -> str:
    ticker = state.get("ticker") or _consensus_view(state).get("ticker", "Research")
    page_title = title or f"{ticker} Consensus + Assumption Research Trace"
    phases = _detect_phases(state)
    if phase != "all" and phase not in phases:
        phase = "all"

    process = build_process_mermaid(state, phase=phase)
    evidence = build_evidence_mermaid(state)
    results = build_results_mermaid(state) if phase in ("all", "consensus") else ""
    exploration = build_exploration_mermaid(state)
    assumption_map_chart = build_assumption_map_mermaid(state) if "assumption" in phases and phase in ("all", "assumption") else ""
    assumption_quality = build_assumption_quality_mermaid(state) if "assumption" in phases and phase in ("all", "assumption") else ""
    conflicts_chart = build_conflicts_mermaid(state)
    priorities_chart = build_priorities_mermaid(state) if "assumption" in phases else ""

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

    assumption_rows = ""
    for row in _assumption_table_rows(state):
        assumption_rows += "<tr>" + "".join(f"<td>{html.escape(c)}</td>" for c in row) + "</tr>\n"

    report = state.get("final_report") or state.get("consensus_report") or ""
    report_pre = html.escape(report[:12000])
    if len(report) > 12000:
        report_pre += "\n\n... (truncated)"

    assumption_report = state.get("assumption_report") or ""
    assumption_report_pre = html.escape(assumption_report[:12000])
    if len(assumption_report) > 12000:
        assumption_report_pre += "\n\n... (truncated)"

    optional_sections = ""
    if results:
        optional_sections += f"""
  <h2>Consensus dimension coverage</h2>
  <div class="mermaid">
{results}
  </div>
"""
    if assumption_map_chart:
        optional_sections += f"""
  <h2>Assumption map</h2>
  <div class="mermaid">
{assumption_map_chart}
  </div>
  <table>
    <tr><th>ID</th><th>Category</th><th>Statement</th><th>Anchor</th><th>Controversy</th><th>Falsification</th><th>Note</th></tr>
    {assumption_rows}
  </table>
"""
    if assumption_quality:
        optional_sections += f"""
  <h2>Assumption quality dimensions</h2>
  <div class="mermaid">
{assumption_quality}
  </div>
"""
    if conflicts_chart:
        optional_sections += f"""
  <h2>Conflicts</h2>
  <div class="mermaid">
{conflicts_chart}
  </div>
"""
    if priorities_chart:
        optional_sections += f"""
  <h2>Research priorities</h2>
  <div class="mermaid">
{priorities_chart}
  </div>
"""

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
  <p>Generated from consensus + assumption research JSON state.</p>

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
{optional_sections}
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

  <h2>Consensus report excerpt</h2>
  <pre>{report_pre}</pre>

  <h2>Assumption report excerpt</h2>
  <pre>{assumption_report_pre}</pre>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
  </script>
</body>
</html>
"""


def render_markdown(state: dict[str, Any], *, phase: str = "all") -> str:
    ticker = state.get("ticker") or _consensus_view(state).get("ticker", "Research")
    lines = [
        f"# {ticker} Consensus + Assumption Research Trace",
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
        build_process_mermaid(state, phase=phase),
        "```",
    ])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visualize consensus + assumption research JSON output")
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
        "--phase",
        choices=["consensus", "assumption", "all"],
        default="all",
        help="Which phase diagrams to emphasize (default: all)",
    )
    parser.add_argument("--title", help="Override page title")
    parser.add_argument(
        "--diagram",
        choices=[
            "process", "evidence", "results", "exploration", "assumption_map",
            "assumptions_quality", "conflicts", "priorities", "all",
        ],
        default="all",
        help="For --format mermaid: which diagram to emit",
    )
    args = parser.parse_args(argv)

    state = _load_state(args.input)

    if args.format == "html":
        content = render_html(state, title=args.title, phase=args.phase)
        out = args.output or args.input.with_suffix(".html")
        out.write_text(content, encoding="utf-8")
        print(f"Wrote {out}")
    elif args.format == "md":
        content = render_markdown(state, phase=args.phase)
        out = args.output
        if out:
            out.write_text(content, encoding="utf-8")
            print(f"Wrote {out}")
        else:
            print(content)
    else:
        builders = {
            "process": lambda s: build_process_mermaid(s, phase=args.phase),
            "evidence": build_evidence_mermaid,
            "results": build_results_mermaid,
            "exploration": build_exploration_mermaid,
            "assumption_map": build_assumption_map_mermaid,
            "assumptions_quality": build_assumption_quality_mermaid,
            "conflicts": build_conflicts_mermaid,
            "priorities": build_priorities_mermaid,
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
