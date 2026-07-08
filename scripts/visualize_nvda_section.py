#!/usr/bin/env python3
"""Visualize section research JSON (execution + content) as HTML/MD/Mermaid."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import webbrowser
from collections import Counter
from pathlib import Path
from typing import Any


def _load_state(path: Path | None) -> dict[str, Any]:
    if path and path.name == "-":
        return json.load(sys.stdin)
    if path:
        return json.loads(path.read_text(encoding="utf-8"))
    raise ValueError("input path required")


def _get_by_path(payload: dict[str, Any], dotted: str) -> Any:
    value: Any = payload
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _resolve_section_output(state: dict[str, Any], section_id: str | None) -> dict[str, Any]:
    if section_id:
        from_map = (state.get("section_research_outputs") or {}).get(section_id)
        if isinstance(from_map, dict):
            return from_map
    if isinstance(state.get("section_research_output"), dict):
        return state["section_research_output"]
    outputs = state.get("section_research_outputs") or {}
    if isinstance(outputs, dict) and outputs:
        first = next(iter(outputs.values()))
        if isinstance(first, dict):
            return first
    return {}


def _resolve_research_plan(state: dict[str, Any], section_output: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        section_output.get("research_plan"),
        state.get("research_plan"),
        _get_by_path(section_output, "subgraph_outputs.section_research.research_plan"),
        _get_by_path(state, "subgraph_outputs.section_research.research_plan"),
    ]
    for c in candidates:
        if isinstance(c, dict) and c.get("tasks"):
            return c
    return {}


def _resolve_research_todos(state: dict[str, Any], section_output: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = [
        _get_by_path(section_output, "subgraph_outputs.section_research.research_todos"),
        _get_by_path(state, "subgraph_outputs.section_research.research_todos"),
        section_output.get("research_todos"),
        state.get("research_todos"),
    ]
    for c in candidates:
        if isinstance(c, list):
            return [x for x in c if isinstance(x, dict)]
    return []


def _resolve_parameter_registry(state: dict[str, Any], section_output: dict[str, Any]) -> dict[str, Any]:
    """Locate the ParameterPreservingReducer registry in the state tree."""
    candidates = [
        section_output.get("parameter_registry"),
        state.get("parameter_registry"),
        _get_by_path(section_output, "subgraph_outputs.section_research.parameter_registry"),
        _get_by_path(state, "subgraph_outputs.section_research.parameter_registry"),
    ]
    for c in candidates:
        if isinstance(c, dict) and (c.get("parameters") or c.get("dimensions")):
            return c
    return {}


def _parameter_table_rows(registry: dict[str, Any]) -> str:
    """Render ParameterRegistry parameters as HTML table rows grouped by dimension."""
    parameters = registry.get("parameters") or {}
    if not parameters:
        return ""

    # Group by dimension
    by_dim: dict[str, list[tuple[str, dict]]] = {}
    for key, param in parameters.items():
        dim = param.get("dimension") or "general"
        by_dim.setdefault(dim, []).append((key, param))

    rows = []
    for dim in sorted(by_dim.keys()):
        # Dimension separator row
        rows.append(
            f'<tr><td colspan="7" style="background:#e8eaf6;font-weight:bold;">'
            f'{html.escape(dim)}</td></tr>'
        )
        for key, param in sorted(by_dim[dim], key=lambda x: x[0]):
            current = param.get("current") or {}
            is_conflict = param.get("is_conflict", False)
            conflict_badge = ' <span style="color:#c62828;">⚠️ CONFLICT</span>' if is_conflict else ""
            row_style = ' style="background:#fff3e0;"' if is_conflict else ""
            # Build history summary
            history = param.get("history") or []
            history_text = ""
            if history:
                entries = []
                for h in history[-3:]:
                    h_val = h.get("value", "?")
                    h_unit = h.get("unit", "")
                    h_as_of = h.get("as_of", "?")
                    entries.append(f"{h_val}{h_unit} ({h_as_of})")
                history_text = " → ".join(entries)

            rows.append(
                f"<tr{row_style}>"
                f"<td><code>{html.escape(str(key))}</code></td>"
                f"<td>{html.escape(str(current.get('value', '?')))}"
                f" {html.escape(str(current.get('unit', '')))}</td>"
                f"<td>{html.escape(str(current.get('as_of', '?')))}</td>"
                f"<td>{html.escape(str(current.get('source', '')))}</td>"
                f"<td>{param.get('confidence', current.get('confidence', '—'))}</td>"
                f"<td>{html.escape(str(len(history)))}</td>"
                f"<td>{conflict_badge}"
                f"{html.escape(history_text) if history_text else '—'}</td>"
                f"</tr>"
            )
    return "\n".join(rows)


def _parameter_grid_pre(registry: dict[str, Any], state: dict[str, Any], section_output: dict[str, Any]) -> str:
    """Return the pre-formatted parameter_grid text if available."""
    grid = (
        section_output.get("parameter_grid")
        or state.get("parameter_grid")
        or _get_by_path(section_output, "subgraph_outputs.section_research.parameter_grid")
        or _get_by_path(state, "subgraph_outputs.section_research.parameter_grid")
        or ""
    )
    return str(grid).strip()


def _safe_id(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", text)


def _label(text: Any, max_len: int = 88) -> str:
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 3] + "..."
    return cleaned.replace('"', "'").replace("[", "(").replace("]", ")")


def _status_color(status: str) -> str:
    m = {
        "done": "#d1fae5",
        "completed": "#d1fae5",
        "in_progress": "#fef3c7",
        "pending": "#fee2e2",
    }
    return m.get((status or "").lower(), "#e5e7eb")


def build_plan_mermaid(plan: dict[str, Any]) -> str:
    tasks = plan.get("tasks") or []
    if not tasks:
        return "flowchart LR\n    empty[No research_plan tasks]"

    lines = ["flowchart TB", '    ROOT["Research Plan"]']
    class_lines = []
    for t in tasks:
        task_id = str(t.get("task_id", "task"))
        tnode = _safe_id(f"task_{task_id}")
        tstatus = str(t.get("status", "pending"))
        objective = _label(t.get("objective", task_id), max_len=70)
        lines.append(f'    {tnode}["{task_id}<br/>{objective}<br/>status={tstatus}"]')
        lines.append(f"    ROOT --> {tnode}")
        color = _status_color(tstatus)
        class_lines.append(f"    style {tnode} fill:{color},stroke:#6b7280,stroke-width:1px")

        steps = sorted(t.get("steps") or [], key=lambda x: int(x.get("order", 0)))
        prev = None
        for s in steps:
            sid = str(s.get("step_id", "step"))
            snode = _safe_id(f"{task_id}_{sid}")
            sstatus = str(s.get("status", "pending"))
            stxt = _label(s.get("action", sid), max_len=36)
            lines.append(f'    {snode}["{sid}<br/>{stxt}<br/>{sstatus}"]')
            if prev is None:
                lines.append(f"    {tnode} --> {snode}")
            else:
                lines.append(f"    {prev} --> {snode}")
            prev = snode
            color = _status_color(sstatus)
            class_lines.append(f"    style {snode} fill:{color},stroke:#9ca3af,stroke-width:1px")

    return "\n".join(lines + class_lines)


def build_todos_mermaid(todos: list[dict[str, Any]]) -> str:
    if not todos:
        return "flowchart LR\n    empty[No research_todos]"

    by_status: dict[str, list[dict[str, Any]]] = {"done": [], "in_progress": [], "pending": [], "other": []}
    for todo in todos:
        status = str(todo.get("status", "other")).lower()
        if status not in by_status:
            status = "other"
        by_status[status].append(todo)

    lines = ["flowchart LR"]
    for status in ["done", "in_progress", "pending", "other"]:
        title = status.upper()
        lines.append(f"    subgraph {status}[{title}]")
        for i, todo in enumerate(by_status[status][:18]):
            node = _safe_id(f"{status}_{i}_{todo.get('item_id', i)}")
            txt = _label(todo.get("title", todo.get("step_id", "todo")), max_len=52)
            lines.append(f'      {node}["{txt}"]')
        lines.append("    end")
    return "\n".join(lines)


def _summary_rows(state: dict[str, Any], section_output: dict[str, Any], plan: dict[str, Any], todos: list[dict[str, Any]]) -> list[tuple[str, str]]:
    tasks = plan.get("tasks") or []
    steps = [s for t in tasks for s in (t.get("steps") or [])]
    done_steps = [s for s in steps if str(s.get("status", "")).lower() in {"done", "completed"}]
    todo_counter = Counter(str(t.get("status", "other")).lower() for t in todos)
    # ParameterPreservingReducer stats
    registry = _resolve_parameter_registry(state, section_output)
    params = registry.get("parameters") or {}
    param_count = len(params)
    conflict_count = sum(1 for p in params.values() if p.get("is_conflict"))
    dim_count = len(registry.get("dimensions") or [])

    return [
        ("Ticker", str(state.get("ticker", "?"))),
        ("Section", str(section_output.get("section_id") or state.get("section_id") or "")),
        ("Section title", str(section_output.get("section_title", ""))),
        ("Plan tasks", str(len(tasks))),
        ("Plan steps", str(len(steps))),
        ("Completed steps", f"{len(done_steps)}/{len(steps)}" if steps else "0/0"),
        ("Todos", str(len(todos))),
        ("Todos done/in_progress/pending", f"{todo_counter.get('done', 0)}/{todo_counter.get('in_progress', 0)}/{todo_counter.get('pending', 0)}"),
        ("Parameters extracted", str(param_count)),
        ("Parameters (conflicts)", str(conflict_count)),
        ("Parameter dimensions", str(dim_count)),
        ("API calls", str(state.get("api_calls", 0))),
        ("Research traces", str(len(state.get('research_traces') or []))),
    ]


def _task_table_rows(plan: dict[str, Any]) -> str:
    rows = []
    for task in plan.get("tasks") or []:
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(task.get('task_id', '')))}</code></td>"
            f"<td><code>{html.escape(str(task.get('question_id', '')))}</code></td>"
            f"<td>{html.escape(str(task.get('task_type', '')))}</td>"
            f"<td>{task.get('priority', '')}</td>"
            f"<td>{html.escape(str(task.get('status', '')))}</td>"
            f"<td>{html.escape(_label(task.get('objective', ''), max_len=150))}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _step_table_rows(plan: dict[str, Any]) -> str:
    rows = []
    for task in plan.get("tasks") or []:
        for step in sorted(task.get("steps") or [], key=lambda x: int(x.get("order", 0))):
            rows.append(
                "<tr>"
                f"<td><code>{html.escape(str(task.get('task_id', '')))}</code></td>"
                f"<td><code>{html.escape(str(step.get('step_id', '')))}</code></td>"
                f"<td>{step.get('order', '')}</td>"
                f"<td>{html.escape(str(step.get('action', '')))}</td>"
                f"<td>{html.escape(str(step.get('status', '')))}</td>"
                f"<td>{html.escape(_label(step.get('description', ''), max_len=200))}</td>"
                "</tr>"
            )
    return "\n".join(rows)


def _todo_table_rows(todos: list[dict[str, Any]]) -> str:
    rows = []
    sorted_todos = sorted(
        todos,
        key=lambda t: (-int(t.get("priority", 0) or 0), str(t.get("status", "")), str(t.get("item_id", ""))),
    )
    for todo in sorted_todos:
        rows.append(
            "<tr>"
            f"<td><code>{html.escape(str(todo.get('item_id', '')))}</code></td>"
            f"<td>{html.escape(str(todo.get('status', '')))}</td>"
            f"<td>{todo.get('priority', '')}</td>"
            f"<td><code>{html.escape(str(todo.get('task_id', '')))}</code></td>"
            f"<td><code>{html.escape(str(todo.get('step_id', '')))}</code></td>"
            f"<td>{html.escape(_label(todo.get('title', ''), max_len=120))}</td>"
            "</tr>"
        )
    return "\n".join(rows)



def _render_parameter_grid_pre(registry: dict[str, Any], state: dict[str, Any], section_output: dict[str, Any]) -> str:
    """Render the parameter_grid text in a <pre> block if non-empty."""
    grid = _parameter_grid_pre(registry, state, section_output)
    if not grid:
        return ""
    return f"""<details>
    <summary><strong>Parameter Grid (raw text)</strong></summary>
    <pre>{html.escape(grid)}</pre>
  </details>"""

def render_html(state: dict[str, Any], *, title: str | None = None, section_filter: str | None = None) -> str:
    section_output = _resolve_section_output(state, section_filter)
    plan = _resolve_research_plan(state, section_output)
    todos = _resolve_research_todos(state, section_output)

    ticker = str(state.get("ticker", "Research"))
    page_title = title or f"{ticker} Section Research Visualization"
    summary_html = "\n".join(
        f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
        for k, v in _summary_rows(state, section_output, plan, todos)
    )
    plan_mermaid = build_plan_mermaid(plan)
    todo_mermaid = build_todos_mermaid(todos)
    executive_summary = str(section_output.get("executive_summary", "")).strip()
    final_text = str(section_output.get("final_section_text", "")).strip()

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
    pre {{ white-space: pre-wrap; word-break: break-word; font-size: 0.88rem; margin: 0; }}
    .mermaid {{ background: #fafafa; padding: 1rem; border-radius: 8px; overflow-x: auto; margin: 1rem 0; }}
    code {{ background: #f0f0f0; padding: 0.1rem 0.3rem; border-radius: 3px; }}
    details {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 0.5rem 1rem 1rem; margin: 1rem 0; }}
    summary {{ cursor: pointer; }}
  </style>
</head>
<body>
  <h1>{html.escape(page_title)}</h1>
  <p>Execution-first view of section research output, then rendered content.</p>

  <h2>Overview</h2>
  <table>{summary_html}</table>

  <h2>Research Plan Flow</h2>
  <div class="mermaid">
{plan_mermaid}
  </div>

  <h2>Research Todo Board</h2>
  <div class="mermaid">
{todo_mermaid}
  </div>

  <h3>Tasks</h3>
  <table>
    <tr><th>Task</th><th>Question</th><th>Type</th><th>Priority</th><th>Status</th><th>Objective</th></tr>
    {_task_table_rows(plan)}
  </table>

  <h3>Steps</h3>
  <table>
    <tr><th>Task</th><th>Step</th><th>Order</th><th>Action</th><th>Status</th><th>Description</th></tr>
    {_step_table_rows(plan)}
  </table>

  <h3>Todos</h3>
  <table>
    <tr><th>Todo ID</th><th>Status</th><th>Priority</th><th>Task</th><th>Step</th><th>Title</th></tr>
    {_todo_table_rows(todos)}
  </table>

  <h2>Parameter Registry</h2>
  <p>Structured parameters extracted by the ParameterPreservingReducer (Map → Reduce → Compile).</p>
  <table>
    <tr><th>Key</th><th>Value</th><th>As Of</th><th>Source</th><th>Confidence</th><th>History</th><th>Status</th></tr>
    {_parameter_table_rows(registry) if (registry := _resolve_parameter_registry(state, section_output)) else '<tr><td colspan="7"><em>No parameters extracted</em></td></tr>'}
  </table>
  {_render_parameter_grid_pre(registry, state, section_output)}

  <h2>Section Content</h2>
  <details open>
    <summary><strong>Executive Summary</strong></summary>
    <pre>{html.escape(executive_summary)}</pre>
  </details>
  <details open>
    <summary><strong>Final Section Text</strong></summary>
    <pre>{html.escape(final_text)}</pre>
  </details>

  <script>
    mermaid.initialize({{ startOnLoad: true, theme: "neutral", securityLevel: "loose" }});
  </script>
</body>
</html>
"""


def render_markdown(state: dict[str, Any], *, section_filter: str | None = None) -> str:
    section_output = _resolve_section_output(state, section_filter)
    plan = _resolve_research_plan(state, section_output)
    todos = _resolve_research_todos(state, section_output)
    lines = [f"# {state.get('ticker', 'Research')} Section Research Visualization", ""]
    lines.extend(["## Overview", "", "| Field | Value |", "|---|---|"])
    for k, v in _summary_rows(state, section_output, plan, todos):
        lines.append(f"| {k} | {v} |")
    lines.extend(["", "## Research Plan", "", "```mermaid", build_plan_mermaid(plan), "```"])
    lines.extend(["", "## Research Todos", "", "```mermaid", build_todos_mermaid(todos), "```"])
    # ParameterPreservingReducer section
    registry = _resolve_parameter_registry(state, section_output)
    if registry:
        lines.extend(["", "## Parameter Registry", ""])
        params = registry.get("parameters") or {}
        if params:
            lines.extend(["| Key | Value | As Of | Source | Conflict |", "|---|---|---|---|---|"])
            for key in sorted(params.keys()):
                p = params[key]
                cur = p.get("current") or {}
                conflict = "⚠️" if p.get("is_conflict") else "✅"
                lines.append(
                    f"| `{key}` | {cur.get('value', '?')} {cur.get('unit', '')} "
                    f"| {cur.get('as_of', '?')} | {cur.get('source', '')} | {conflict} |"
                )
        grid = _parameter_grid_pre(registry, state, section_output)
        if grid:
            lines.extend(["", "### Parameter Grid", "", "```", grid, "```"])

    lines.extend(
        [
            "",
            "## Section Content",
            "",
            "### Executive Summary",
            "",
            str(section_output.get("executive_summary", "")),
            "",
            "### Final Section Text",
            "",
            str(section_output.get("final_section_text", "")),
        ]
    )
    return "\n".join(lines)


def render_mermaid(state: dict[str, Any], *, section_filter: str | None = None) -> str:
    section_output = _resolve_section_output(state, section_filter)
    plan = _resolve_research_plan(state, section_output)
    todos = _resolve_research_todos(state, section_output)
    return "\n\n".join([build_plan_mermaid(plan), build_todos_mermaid(todos)])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Visualize out/nvda_section.json")
    parser.add_argument(
        "input",
        nargs="?",
        type=Path,
        default=Path("out/nvda_section.json"),
        help="Path to section JSON (default: out/nvda_section.json; use - for stdin)",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output file path")
    parser.add_argument("--format", choices=["html", "md", "mermaid"], default="html")
    parser.add_argument("--title", help="Override page title")
    parser.add_argument("--section-id", help="Render a specific section id if present")
    parser.add_argument("--open", action="store_true", help="Open generated output in browser")
    args = parser.parse_args(argv)

    state = _load_state(args.input)
    if args.format == "html":
        content = render_html(state, title=args.title, section_filter=args.section_id)
        default_out = args.input.with_suffix(".html")
    elif args.format == "md":
        content = render_markdown(state, section_filter=args.section_id)
        default_out = args.input.with_suffix(".md")
    else:
        content = render_mermaid(state, section_filter=args.section_id)
        default_out = args.input.with_suffix(".mmd")

    out_path = args.output or default_out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")
    print(f"Wrote {out_path}")

    if args.open and args.format == "html":
        webbrowser.open(out_path.resolve().as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
