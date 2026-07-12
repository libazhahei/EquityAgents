#!/usr/bin/env python3
"""Visualize equity research E2E spine JSON (demo_equity_research run bundle).

Pass a **run name** (as produced by ``demo_equity_research -o``) and this script
loads **all** companion JSON files for that run, then renders one HTML/MD report.

Name resolution (``--root`` defaults to ``out/``):

  nvda_equity_e2e
    → out/nvda_equity_e2e.json
    → out/nvda_equity_e2e.progress_events.json
    → out/nvda_equity_e2e.research_traces.json
    → out/nvda_equity_e2e.run_summary.json
    → out/nvda_equity_e2e.run_tree.json

  NVDA_equity_20260712_072000   (directory bundle)
    → out/NVDA_equity_.../full_state.json + companions

Examples:
  uv run python scripts/visualize_equity_research_trace.py nvda_equity_e2e
  uv run python scripts/visualize_equity_research_trace.py nvda_equity_e2e -o out/nvda_equity_e2e.html
  uv run python scripts/visualize_equity_research_trace.py out/nvda_equity_e2e.json
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_PARENT_STAGES = [
    "initialize_state",
    "consensus",
    "assumption",
    "human_review_1",
    "planner",
    "human_review_2",
    "pick_next_section",
    "section_research",
]

# Companion suffixes written by demo_equity_research.save_run_bundle
_COMPANION_KINDS = (
    "progress_events",
    "research_traces",
    "run_summary",
    "run_tree",
)


@dataclass
class RunBundle:
    """All JSON artifacts for one demo_equity_research run."""

    name: str
    root: Path
    state_path: Path
    state: dict[str, Any]
    files: dict[str, Path] = field(default_factory=dict)
    progress_events: list[dict[str, Any]] = field(default_factory=list)
    research_traces: list[dict[str, Any]] = field(default_factory=list)
    run_summary: dict[str, Any] = field(default_factory=dict)
    run_tree: list[dict[str, Any]] = field(default_factory=list)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _strip_name(raw: str) -> str:
    """Normalize user-provided name: drop .json / full_state / path noise."""
    text = raw.strip().rstrip("/\\")
    p = Path(text)
    name = p.name
    if name == "full_state.json":
        return p.parent.name
    if name.endswith(".json"):
        # nvda_equity_e2e.progress_events.json → nvda_equity_e2e
        stem = Path(name).stem
        for kind in _COMPANION_KINDS:
            suffix = f".{kind}"
            if stem.endswith(suffix):
                return stem[: -len(suffix)]
        return stem
    return name


def discover_bundle_files(name: str, *, root: Path = Path("out")) -> dict[str, Path]:
    """Find all demo_equity_research JSON files for a run name.

    Supports:
    - stem layout: ``{root}/{name}.json`` + ``{root}/{name}.{kind}.json``
    - dir layout:  ``{root}/{name}/full_state.json`` + companions
    - absolute/relative path to either form
    """
    raw = Path(name)
    files: dict[str, Path] = {}

    # Explicit path to a json file
    if raw.suffix.lower() == ".json" and raw.exists():
        stem_name = _strip_name(str(raw))
        parent = raw.parent
        # Prefer stem siblings next to this file
        primary = parent / f"{stem_name}.json"
        if not primary.exists() and raw.name == "full_state.json":
            primary = raw
            dir_base = parent
            files["full_state"] = primary
            for kind in _COMPANION_KINDS:
                p = dir_base / f"{kind}.json"
                if p.exists():
                    files[kind] = p
            return files
        if primary.exists():
            files["full_state"] = primary
        elif raw.exists():
            files["full_state"] = raw
            stem_name = raw.stem
        for kind in _COMPANION_KINDS:
            p = parent / f"{stem_name}.{kind}.json"
            if p.exists():
                files[kind] = p
        return files

    # Explicit directory
    if raw.is_dir():
        full = raw / "full_state.json"
        if full.exists():
            files["full_state"] = full
            for kind in _COMPANION_KINDS:
                p = raw / f"{kind}.json"
                if p.exists():
                    files[kind] = p
            return files

    stem = _strip_name(name)

    # Directory bundle under root
    dir_bundle = root / stem
    if dir_bundle.is_dir() and (dir_bundle / "full_state.json").exists():
        files["full_state"] = dir_bundle / "full_state.json"
        for kind in _COMPANION_KINDS:
            p = dir_bundle / f"{kind}.json"
            if p.exists():
                files[kind] = p
        return files

    # Stem-prefixed files under root (and also if name already includes out/)
    search_dirs = [root]
    if raw.parent != Path("."):
        search_dirs.insert(0, raw.parent)

    for base in search_dirs:
        primary = base / f"{stem}.json"
        if primary.exists():
            files["full_state"] = primary
            for kind in _COMPANION_KINDS:
                p = base / f"{stem}.{kind}.json"
                if p.exists():
                    files[kind] = p
            return files

    raise FileNotFoundError(
        f"No demo_equity_research JSON bundle found for name={name!r} under {root}/ "
        f"(expected {root / (stem + '.json')} or {root / stem / 'full_state.json'})"
    )


def load_run_bundle(name: str, *, root: Path = Path("out")) -> RunBundle:
    """Resolve name and load every companion JSON into a RunBundle."""
    files = discover_bundle_files(name, root=root)
    state_path = files["full_state"]
    state = _load_json(state_path)
    if not isinstance(state, dict):
        raise ValueError(f"{state_path} must be a JSON object")

    progress: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    summary: dict[str, Any] = {}
    tree: list[dict[str, Any]] = []

    if "progress_events" in files:
        data = _load_json(files["progress_events"])
        if isinstance(data, list):
            progress = data
    elif isinstance(state.get("progress_events"), list):
        progress = list(state["progress_events"])

    if "research_traces" in files:
        data = _load_json(files["research_traces"])
        if isinstance(data, list):
            traces = data
            # Prefer sidecar traces if state is missing/empty
            if not state.get("research_traces"):
                state = {**state, "research_traces": traces}
    else:
        traces = list(state.get("research_traces") or [])

    if "run_summary" in files:
        data = _load_json(files["run_summary"])
        if isinstance(data, dict):
            summary = data

    if "run_tree" in files:
        data = _load_json(files["run_tree"])
        if isinstance(data, list):
            tree = data
    else:
        tree = list(state.get("run_tree") or [])

    return RunBundle(
        name=_strip_name(name),
        root=root,
        state_path=state_path,
        state=state,
        files=files,
        progress_events=progress,
        research_traces=traces,
        run_summary=summary,
        run_tree=tree,
    )


def _mermaid_id(text: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in str(text))


def _esc_label(text: str, *, max_len: int = 80) -> str:
    cleaned = " ".join(str(text).split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned.replace('"', "'").replace("[", "(").replace("]", ")")


def build_spine_mermaid(state: dict[str, Any], progress: list[dict[str, Any]]) -> str:
    """Parent graph spine with status badges from progress events."""
    status_by_stage: dict[str, str] = {}
    for ev in progress:
        stage = ev.get("stage") or ev.get("node") or ""
        if stage:
            status_by_stage[stage] = str(ev.get("status") or "")

    selected = state.get("selected_section_ids") or []
    lines = ["flowchart LR"]
    prev = None
    for stage in _PARENT_STAGES:
        nid = _mermaid_id(stage)
        status = status_by_stage.get(stage, "")
        label = stage
        if status:
            label = f"{stage}<br/>{status}"
        if stage == "section_research" and selected:
            label += f"<br/>{', '.join(selected[:3])}"
        lines.append(f'    {nid}["{_esc_label(label, max_len=120)}"]')
        if prev:
            lines.append(f"    {prev} --> {nid}")
        prev = nid
    return "\n".join(lines)


def build_progress_timeline_mermaid(progress: list[dict[str, Any]], *, limit: int = 40) -> str:
    if not progress:
        return "flowchart LR\n    empty[No progress_events]"

    lines = ["flowchart TD"]
    prev = None
    for i, ev in enumerate(progress[:limit]):
        nid = f"p{i}"
        stage = ev.get("stage") or "?"
        status = ev.get("status") or "?"
        section = ev.get("section_id") or ""
        label = f"{stage} / {status}"
        if section:
            label += f"<br/>{section}"
        lines.append(f'    {nid}["{_esc_label(label, max_len=100)}"]')
        if prev is not None:
            lines.append(f"    {prev} --> {nid}")
        prev = nid
    if len(progress) > limit:
        lines.append(f'    more["… +{len(progress) - limit} more events"]')
        if prev is not None:
            lines.append(f"    {prev} --> more")
    return "\n".join(lines)


def build_trace_mermaid(state: dict[str, Any], *, limit: int = 50) -> str:
    traces = state.get("research_traces") or []
    if not traces:
        return "flowchart LR\n    empty[No research_traces]"

    lines = ["flowchart TD"]
    prev = None
    for i, t in enumerate(traces[:limit]):
        name = t.get("node_name") or f"trace_{i}"
        nid = _mermaid_id(f"t_{i}_{name}")
        payload = t.get("payload") or {}
        bits = [name.replace("_", " ")]
        if "iterations" in payload:
            bits.append(f"iter={payload['iterations']}")
        if "section_id" in payload:
            bits.append(str(payload["section_id"]))
        if "overall_score" in payload:
            bits.append(f"score={payload['overall_score']}")
        if "status" in payload:
            bits.append(str(payload["status"]))
        label = "<br/>".join(_esc_label(b, max_len=60) for b in bits)
        lines.append(f'    {nid}["{label}"]')
        if prev:
            lines.append(f"    {prev} --> {nid}")
        prev = nid
    return "\n".join(lines)


def build_run_tree_mermaid(run_tree: list[dict[str, Any]]) -> str:
    if not run_tree:
        return "flowchart LR\n    empty[No run_tree]"

    lines = ["flowchart TB"]
    for row in run_tree:
        path = row.get("node_path") or "?"
        nid = _mermaid_id(path)
        status = row.get("status") or ""
        section = row.get("section_id") or ""
        label = f"{path}<br/>{status}"
        if section:
            label += f"<br/>{section}"
        lines.append(f'    {nid}["{_esc_label(label, max_len=120)}"]')
        if "/" in path:
            parent = path.split("/", 1)[0]
            if any(r.get("node_path") == parent for r in run_tree):
                lines.append(f"    {_mermaid_id(parent)} --> {nid}")
    top = [r.get("node_path") for r in run_tree if r.get("node_path") and "/" not in str(r.get("node_path"))]
    for a, b in zip(top, top[1:]):
        if a and b:
            lines.append(f"    {_mermaid_id(a)} --> {_mermaid_id(b)}")
    return "\n".join(lines)


def build_sections_mermaid(state: dict[str, Any]) -> str:
    plans = state.get("section_plans") or {}
    outputs = state.get("section_research_outputs") or {}
    selected = set(state.get("selected_section_ids") or [])
    if not plans and not outputs:
        return "flowchart LR\n    empty[No sections]"

    lines = ["flowchart TB", '    ROOT["Sections"]']
    ids = list(dict.fromkeys([*selected, *outputs.keys(), *plans.keys()]))
    for sid in ids[:12]:
        nid = _mermaid_id(sid)
        flags = []
        if sid in selected:
            flags.append("selected")
        if sid in outputs:
            flags.append("researched")
        elif sid in plans:
            flags.append("planned")
        title = (plans.get(sid) or {}).get("section_title") or sid
        label = f"{sid}<br/>{_esc_label(title, max_len=40)}<br/>{', '.join(flags)}"
        lines.append(f'    {nid}["{label}"]')
        lines.append(f"    ROOT --> {nid}")
    return "\n".join(lines)


def _summary_rows(
    state: dict[str, Any],
    progress: list[dict[str, Any]],
    run_tree: list[dict[str, Any]],
    *,
    run_summary: dict[str, Any] | None = None,
    files: dict[str, Path] | None = None,
) -> list[tuple[str, str]]:
    cv = state.get("consensus_view") or {}
    av = state.get("assumption_view") or {}
    amap = av.get("assumption_map") or state.get("assumption_map") or []
    rows = [
        ("Ticker", str(state.get("ticker", "?"))),
        ("Run id", str(state.get("run_id", ""))),
        ("Trade date", str(state.get("trade_date", ""))),
        ("Report id", str(state.get("report_id", ""))),
        ("Consensus coverage", str(cv.get("coverage_score", "n/a"))),
        ("Assumption items", str(len(amap))),
        ("Section plans", str(len(state.get("section_plans") or {}))),
        ("Selected sections", ", ".join(state.get("selected_section_ids") or []) or "(none)"),
        ("Researched sections", ", ".join((state.get("section_research_outputs") or {}).keys()) or "(none)"),
        ("Progress events", str(len(progress))),
        ("Research traces", str(len(state.get("research_traces") or []))),
        ("Run-tree edges", str(len(run_tree))),
        ("API calls", str(state.get("api_calls", 0))),
        ("Errors", str(len(state.get("errors") or []))),
        ("Warnings", str(len(state.get("warnings") or []))),
    ]
    if files:
        rows.append(("Bundle files", ", ".join(sorted(files.keys()))))
    if run_summary:
        rows.append(("Run summary stages", ", ".join(run_summary.get("stages_seen") or []) or "(n/a)"))
    return rows


def _files_table_rows(files: dict[str, Path]) -> str:
    rows = ""
    for kind, path in sorted(files.items()):
        size = path.stat().st_size if path.exists() else 0
        rows += (
            "<tr>"
            f"<td><code>{html.escape(kind)}</code></td>"
            f"<td><code>{html.escape(str(path))}</code></td>"
            f"<td>{size:,}</td>"
            "</tr>\n"
        )
    return rows


def _progress_table_rows(progress: list[dict[str, Any]]) -> str:
    rows = ""
    for ev in progress:
        rows += (
            "<tr>"
            f"<td>{html.escape(str(ev.get('ts', '')))}</td>"
            f"<td><code>{html.escape(str(ev.get('stage', '')))}</code></td>"
            f"<td>{html.escape(str(ev.get('status', '')))}</td>"
            f"<td>{html.escape(str(ev.get('section_id') or ''))}</td>"
            f"<td><pre>{html.escape(json.dumps(ev.get('payload') or {}, ensure_ascii=False))}</pre></td>"
            "</tr>\n"
        )
    return rows


def _trace_table_rows(traces: list[dict[str, Any]]) -> str:
    rows = ""
    for t in traces:
        payload = t.get("payload") or {}
        rows += (
            "<tr>"
            f"<td><code>{html.escape(str(t.get('node_name', '')))}</code></td>"
            f"<td><pre>{html.escape(json.dumps(payload, ensure_ascii=False))}</pre></td>"
            "</tr>\n"
        )
    return rows


def _summary_json_pre(run_summary: dict[str, Any]) -> str:
    if not run_summary:
        return "(no run_summary.json)"
    return html.escape(json.dumps(run_summary, indent=2, ensure_ascii=False, default=str))


def _blackboard_summaries_by_section(state: dict[str, Any]) -> dict[str, str]:
    """Map section_id → summary text from session_blackboard_summaries."""
    out: dict[str, str] = {}
    for item in state.get("session_blackboard_summaries") or []:
        if not isinstance(item, dict):
            continue
        sid = str(item.get("section_id") or "")
        if sid:
            out[sid] = str(item.get("summary") or "")
    return out


def _blackboard_section_ids(state: dict[str, Any]) -> list[str]:
    """Ordered section ids that have blackboard entries and/or summaries."""
    boards = state.get("session_blackboards") or {}
    summaries = _blackboard_summaries_by_section(state)
    ids: list[str] = []
    for sid in boards:
        if sid not in ids:
            ids.append(sid)
    for sid in summaries:
        if sid not in ids:
            ids.append(sid)
    # Prefer research output order when available
    outputs = state.get("section_research_outputs") or {}
    ordered = [sid for sid in outputs if sid in ids]
    ordered.extend(sid for sid in ids if sid not in ordered)
    return ordered


def _blackboard_entries_table_rows(entries: list[dict[str, Any]]) -> str:
    if not entries:
        return '<tr><td colspan="6"><em>(no entries)</em></td></tr>'
    rows = ""
    for entry in entries:
        tags = entry.get("tags") or []
        tags_str = ", ".join(str(t) for t in tags[:8])
        conf = entry.get("confidence", "")
        conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else str(conf)
        rows += (
            "<tr>"
            f"<td><code>{html.escape(str(entry.get('entry_type', '')))}</code></td>"
            f"<td>{html.escape(str(entry.get('content', '')))}</td>"
            f"<td>{html.escape(tags_str)}</td>"
            f"<td>{html.escape(conf_str)}</td>"
            f"<td><code>{html.escape(str(entry.get('source_node', '')))}</code></td>"
            f"<td>{html.escape(str(entry.get('created_at_iteration', '')))}</td>"
            "</tr>\n"
        )
    return rows


def _blackboard_html_blocks(state: dict[str, Any]) -> str:
    """Per-section summary + entries table for HTML visualization."""
    boards = state.get("session_blackboards") or {}
    summaries = _blackboard_summaries_by_section(state)
    section_ids = _blackboard_section_ids(state)
    if not section_ids:
        return "<p>(no session blackboard data)</p>"

    blocks = ""
    for sid in section_ids:
        summary = summaries.get(sid, "")
        entries = boards.get(sid) or []
        if not isinstance(entries, list):
            entries = []
        summary_html = (
            f"<pre>{html.escape(summary)}</pre>"
            if summary
            else "<p><em>(no summary)</em></p>"
        )
        blocks += f"""
  <h3>{html.escape(sid)}</h3>
  <h4>Summary</h4>
  {summary_html}
  <h4>Entries ({len(entries)})</h4>
  <table>
    <tr><th>Type</th><th>Content</th><th>Tags</th><th>Confidence</th><th>Source</th><th>Iter</th></tr>
    {_blackboard_entries_table_rows(entries)}
  </table>
"""
    return blocks


def _blackboard_markdown_blocks(state: dict[str, Any]) -> list[str]:
    """Per-section summary + entries table for Markdown visualization."""
    boards = state.get("session_blackboards") or {}
    summaries = _blackboard_summaries_by_section(state)
    section_ids = _blackboard_section_ids(state)
    lines = ["## Session Blackboard", ""]
    if not section_ids:
        lines.append("(no session blackboard data)")
        return lines

    for sid in section_ids:
        summary = summaries.get(sid, "")
        entries = boards.get(sid) or []
        if not isinstance(entries, list):
            entries = []
        lines.extend([f"### {sid}", "", "#### Summary", "", summary or "*(no summary)*", ""])
        lines.extend([
            f"#### Entries ({len(entries)})",
            "",
            "| Type | Content | Tags | Confidence | Source | Iter |",
            "|------|---------|------|------------|--------|------|",
        ])
        if not entries:
            lines.append("| — | *(no entries)* | | | | |")
        else:
            for entry in entries:
                tags = ", ".join(str(t) for t in (entry.get("tags") or [])[:8])
                conf = entry.get("confidence", "")
                conf_str = f"{conf:.2f}" if isinstance(conf, (int, float)) else str(conf)
                content = " ".join(str(entry.get("content", "")).split()).replace("|", "\\|")
                lines.append(
                    f"| `{entry.get('entry_type', '')}` | {content} | {tags} "
                    f"| {conf_str} | `{entry.get('source_node', '')}` "
                    f"| {entry.get('created_at_iteration', '')} |"
                )
        lines.append("")
    return lines


def render_html(
    state: dict[str, Any],
    *,
    progress_events: list[dict[str, Any]] | None = None,
    run_tree: list[dict[str, Any]] | None = None,
    research_traces: list[dict[str, Any]] | None = None,
    run_summary: dict[str, Any] | None = None,
    files: dict[str, Path] | None = None,
    title: str | None = None,
    bundle_name: str | None = None,
) -> str:
    progress = progress_events if progress_events is not None else []
    tree = run_tree if run_tree is not None else []
    traces = research_traces if research_traces is not None else list(state.get("research_traces") or [])
    # Ensure diagrams see traces even if only loaded from sidecar
    if traces and not state.get("research_traces"):
        state = {**state, "research_traces": traces}

    ticker = state.get("ticker", "Research")
    page_title = title or f"{ticker} Equity Research E2E Trace"
    if bundle_name:
        page_title = f"{page_title} — {bundle_name}"

    spine = build_spine_mermaid(state, progress)
    timeline = build_progress_timeline_mermaid(progress)
    traces_chart = build_trace_mermaid(state)
    sections = build_sections_mermaid(state)
    tree_chart = build_run_tree_mermaid(tree)

    summary_html = "\n".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in _summary_rows(
            state, progress, tree, run_summary=run_summary, files=files,
        )
    )

    files_section = ""
    if files:
        files_section = f"""
  <h2>Bundle JSON files</h2>
  <table>
    <tr><th>Kind</th><th>Path</th><th>Bytes</th></tr>
    {_files_table_rows(files)}
  </table>
"""

    consensus_report = html.escape(str(state.get("consensus_report") or "")[:8000])
    assumption_report = html.escape(str(state.get("assumption_report") or "")[:8000])

    section_blocks = ""
    for sid, out in (state.get("section_research_outputs") or {}).items():
        text = out.get("final_section_text") or out.get("executive_summary") or ""
        section_blocks += (
            f"<h3>{html.escape(sid)}</h3>"
            f"<pre>{html.escape(str(text)[:6000])}</pre>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(page_title)}</title>
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 1200px; line-height: 1.5; }}
    h1, h2, h3 {{ margin-top: 2rem; }}
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
  <p>Loaded all demo_equity_research JSON companions for this run name.</p>

  <h2>Summary</h2>
  <table>{summary_html}</table>
{files_section}
  <h2>Run summary JSON</h2>
  <pre>{_summary_json_pre(run_summary or {})}</pre>

  <h2>Parent spine</h2>
  <div class="mermaid">
{spine}
  </div>

  <h2>Progress timeline</h2>
  <div class="mermaid">
{timeline}
  </div>

  <h2>Run-tree index</h2>
  <div class="mermaid">
{tree_chart}
  </div>

  <h2>Sections</h2>
  <div class="mermaid">
{sections}
  </div>

  <h2>Research traces (subgraph nodes)</h2>
  <div class="mermaid">
{traces_chart}
  </div>

  <h2>Progress events</h2>
  <table>
    <tr><th>Time</th><th>Stage</th><th>Status</th><th>Section</th><th>Payload</th></tr>
    {_progress_table_rows(progress)}
  </table>

  <h2>Trace payload table</h2>
  <table>
    <tr><th>Node</th><th>Payload</th></tr>
    {_trace_table_rows(traces)}
  </table>

  <h2>Consensus report excerpt</h2>
  <pre>{consensus_report}</pre>

  <h2>Assumption report excerpt</h2>
  <pre>{assumption_report}</pre>

  <h2>Section research outputs</h2>
  {section_blocks or "<p>(none)</p>"}

  <h2>Session Blackboard</h2>
  {_blackboard_html_blocks(state)}

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
  </script>
</body>
</html>
"""


def render_markdown(
    state: dict[str, Any],
    *,
    progress_events: list[dict[str, Any]] | None = None,
    run_tree: list[dict[str, Any]] | None = None,
    run_summary: dict[str, Any] | None = None,
    files: dict[str, Path] | None = None,
    bundle_name: str | None = None,
) -> str:
    progress = progress_events or []
    tree = run_tree or []
    ticker = state.get("ticker", "Research")
    heading = f"{ticker} Equity Research E2E Trace"
    if bundle_name:
        heading = f"{heading} — {bundle_name}"
    lines = [
        f"# {heading}",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
    ]
    for k, v in _summary_rows(
        state, progress, tree, run_summary=run_summary, files=files,
    ):
        lines.append(f"| {k} | {v} |")
    if files:
        lines.extend(["", "## Bundle files", ""])
        for kind, path in sorted(files.items()):
            lines.append(f"- `{kind}`: `{path}`")
    lines.extend([
        "",
        "## Parent spine",
        "",
        "```mermaid",
        build_spine_mermaid(state, progress),
        "```",
        "",
        "## Progress timeline",
        "",
        "```mermaid",
        build_progress_timeline_mermaid(progress),
        "```",
        "",
    ])
    lines.extend(_blackboard_markdown_blocks(state))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Visualize a demo_equity_research run by name — loads all companion JSON "
            "files (full state, progress, traces, summary, run_tree)."
        ),
    )
    parser.add_argument(
        "name",
        help=(
            "Run name or path, e.g. nvda_equity_e2e, out/nvda_equity_e2e.json, "
            "or a bundle directory under --root"
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("out"),
        help="Directory to search for named bundles (default: out)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        help="Output file (.html or .md); default: {root}/{name}.html",
    )
    parser.add_argument(
        "--format",
        choices=["html", "md", "mermaid"],
        default="html",
        help="Output format (default: html)",
    )
    parser.add_argument("--title", help="Override page title")
    parser.add_argument(
        "--diagram",
        choices=["spine", "progress", "traces", "sections", "run_tree", "all"],
        default="all",
        help="For --format mermaid: which diagram to emit",
    )
    parser.add_argument(
        "--list-files",
        action="store_true",
        help="Only list discovered JSON files for the name, then exit",
    )
    args = parser.parse_args(argv)

    bundle = load_run_bundle(args.name, root=args.root)

    if args.list_files:
        print(f"Bundle: {bundle.name}")
        for kind, path in sorted(bundle.files.items()):
            print(f"  {kind}: {path} ({path.stat().st_size:,} bytes)")
        return 0

    print(f"Loaded {len(bundle.files)} JSON file(s) for {bundle.name!r}:")
    for kind, path in sorted(bundle.files.items()):
        print(f"  {kind}: {path}")

    if args.format == "html":
        content = render_html(
            bundle.state,
            progress_events=bundle.progress_events,
            run_tree=bundle.run_tree,
            research_traces=bundle.research_traces,
            run_summary=bundle.run_summary,
            files=bundle.files,
            title=args.title,
            bundle_name=bundle.name,
        )
        out = args.output or (args.root / f"{bundle.name}.html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(content, encoding="utf-8")
        print(f"Wrote {out}")
    elif args.format == "md":
        content = render_markdown(
            bundle.state,
            progress_events=bundle.progress_events,
            run_tree=bundle.run_tree,
            run_summary=bundle.run_summary,
            files=bundle.files,
            bundle_name=bundle.name,
        )
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(content)
    else:
        builders = {
            "spine": lambda: build_spine_mermaid(bundle.state, bundle.progress_events),
            "progress": lambda: build_progress_timeline_mermaid(bundle.progress_events),
            "traces": lambda: build_trace_mermaid(bundle.state),
            "sections": lambda: build_sections_mermaid(bundle.state),
            "run_tree": lambda: build_run_tree_mermaid(bundle.run_tree),
        }
        if args.diagram == "all":
            content = "\n\n".join(f"%% {name}\n{fn()}" for name, fn in builders.items())
        else:
            content = builders[args.diagram]()
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
