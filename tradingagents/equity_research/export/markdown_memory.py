"""Export human-readable research memory to filesystem."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def export_research_memory(state: dict[str, Any], config: dict[str, Any] | None = None) -> str:
    config = config or {}
    home = os.path.join(os.path.expanduser("~"), ".tradingagents", "equity_research")
    ticker = state.get("ticker", "UNKNOWN")
    report_id = state.get("report_id", "unknown")
    out_dir = Path(config.get("equity_research_results_dir", os.path.join(home, ticker, report_id)))
    out_dir.mkdir(parents=True, exist_ok=True)

    md_path = out_dir / "research_memory.md"
    json_path = out_dir / "full_state.json"

    lines = [
        f"# Research Memory: {ticker}",
        f"Report ID: {report_id}",
        f"Exported: {datetime.utcnow().isoformat()}",
        "",
        "## Final Report",
        state.get("final_report", ""),
        "",
        "## Verified Hypotheses",
    ]
    for hid in state.get("verified_hypothesis_ids", []):
        node = state.get("hypothesis_nodes", {}).get(hid, {})
        lines.append(f"- {node.get('statement', hid)}")

    lines.extend(["", "## Claims", ""])
    for claim in state.get("claims", []):
        lines.append(f"- [{claim.get('status')}] {claim.get('text', '')[:200]}")

    lines.extend(["", "## Traces", f"Total: {len(state.get('research_traces', []))}"])

    md_path.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    return str(md_path)
