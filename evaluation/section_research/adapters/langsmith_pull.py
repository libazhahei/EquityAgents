"""Pull LangSmith runs and reconstruct an EvalBundle."""

from __future__ import annotations

import json
import logging
from typing import Any

from langsmith import Client

from evaluation.section_research.evaluators.faithfulness import build_evidence_pack
from evaluation.section_research.types import ChildRunSummary, EvalBundle, EvidencePack, FixtureMeta

logger = logging.getLogger(__name__)


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump()
        except Exception:
            pass
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"raw": value}
        except json.JSONDecodeError:
            return {"raw": value}
    return {"raw": str(value)}


def _tool_output_from_child(child: Any) -> dict[str, Any] | None:
    name = getattr(child, "name", None) or ""
    run_type = getattr(child, "run_type", None) or ""
    if run_type != "tool" and not name:
        return None
    return {
        "name": name,
        "run_type": run_type,
        "inputs": _as_dict(getattr(child, "inputs", None)),
        "outputs": _as_dict(getattr(child, "outputs", None)),
        "error": getattr(child, "error", None),
    }


def collect_trace_evidence(
    run_id: str,
    *,
    client: Client | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    """Aggregate tool outputs / citations / evidence from a LangSmith run tree.

    Returns a dict shaped for Faithfulness Evaluation (feedback3 §8).
    """
    ls = client or Client()
    root = ls.read_run(run_id, load_child_runs=True)
    children = list(getattr(root, "child_runs", None) or [])

    # Flatten one more level if present
    flat: list[Any] = []
    stack = list(children)
    while stack:
        node = stack.pop()
        flat.append(node)
        stack.extend(list(getattr(node, "child_runs", None) or []))

    tool_outputs: list[dict[str, Any]] = []
    for child in flat:
        item = _tool_output_from_child(child)
        if item is not None:
            tool_outputs.append(item)

    outputs = _as_dict(getattr(root, "outputs", None))
    inputs = _as_dict(getattr(root, "inputs", None))

    # Prefer nested state-like payloads commonly produced by LangGraph
    state_like = (
        outputs.get("section_research_output")
        or outputs.get("output")
        or outputs
    )
    if not isinstance(state_like, dict):
        state_like = {"raw_outputs": outputs}

    citations = list(state_like.get("citations") or [])
    evidence_ledger = list(state_like.get("evidence_ledger") or outputs.get("evidence_ledger") or [])
    pending_evidence = list(
        state_like.get("pending_evidence") or outputs.get("pending_evidence") or []
    )
    search_memory = list(state_like.get("search_memory") or outputs.get("search_memory") or [])
    if outputs.get("citations") and isinstance(outputs.get("citations"), list):
        citations = list(citations) + list(outputs["citations"])

    # Also scan tool outputs for embedded evidence dumps
    for toot in tool_outputs:
        out = toot.get("outputs") or {}
        if isinstance(out, dict):
            if out.get("citations"):
                citations.extend(out["citations"] if isinstance(out["citations"], list) else [out["citations"]])
            if out.get("evidence_ledger"):
                evidence_ledger.extend(
                    out["evidence_ledger"]
                    if isinstance(out["evidence_ledger"], list)
                    else [out["evidence_ledger"]]
                )

    child_summaries = [
        ChildRunSummary(
            name=str(getattr(c, "name", "") or ""),
            run_type=str(getattr(c, "run_type", "") or ""),
            inputs=_as_dict(getattr(c, "inputs", None)),
            outputs=_as_dict(getattr(c, "outputs", None)) or None,
            error=getattr(c, "error", None),
        )
        for c in flat
    ]

    nested_input = inputs.get("input") if isinstance(inputs.get("input"), dict) else {}
    ticker_val = (
        state_like.get("ticker")
        or inputs.get("ticker")
        or nested_input.get("ticker")
        or ""
    )
    section_val = (
        state_like.get("section_id")
        or inputs.get("section_id")
        or inputs.get("active_section_id")
        or nested_input.get("section_id")
        or nested_input.get("active_section_id")
        or ""
    )
    final_state: dict[str, Any] = {
        "ticker": ticker_val,
        "section_id": section_val,
    }

    # Promote common demo fields when present on outputs
    for key in (
        "section_research_output",
        "section_research_outputs",
        "final_report",
        "research_plan",
        "research_todo_list",
        "answer_cards",
        "coverage_report",
        "research_traces",
        "documents",
        "api_calls",
        "evidence_ledger",
        "pending_evidence",
        "citations",
    ):
        if key in outputs:
            final_state[key] = outputs[key]
        elif key in state_like and key not in final_state:
            final_state[key] = state_like[key]

    if "section_research_output" not in final_state and isinstance(state_like, dict):
        if state_like.get("final_section_text") or state_like.get("executive_summary"):
            final_state["section_research_output"] = state_like

    evidence = EvidencePack(
        tool_outputs=tool_outputs,
        citations=citations,
        evidence_ledger=evidence_ledger,
        pending_evidence=pending_evidence,
        search_memory=search_memory,
    )

    return {
        "tool_outputs": tool_outputs,
        "citations": citations,
        "evidence_ledger": evidence_ledger,
        "pending_evidence": pending_evidence,
        "search_memory": search_memory,
        "final_state": final_state,
        "child_runs": child_summaries,
        "root_name": getattr(root, "name", None),
        "project_name": project_name,
        "evidence": evidence,
    }


def bundle_from_langsmith(
    run_id: str,
    *,
    fixture: FixtureMeta | None = None,
    project_name: str | None = None,
    client: Client | None = None,
) -> EvalBundle:
    packed = collect_trace_evidence(run_id, client=client, project_name=project_name)
    final_state = packed["final_state"]
    meta = fixture or FixtureMeta(
        case_id=f"langsmith:{run_id}",
        ticker=str(final_state.get("ticker") or "UNKNOWN").upper(),
        section_id=str(final_state.get("section_id") or "unknown"),
    )
    ticker = str(final_state.get("ticker") or meta.ticker or "UNKNOWN").upper()
    section_id = str(final_state.get("section_id") or meta.section_id or "unknown")
    final_state.setdefault("ticker", ticker)
    final_state.setdefault("section_id", section_id)

    evidence = packed.get("evidence")
    if not isinstance(evidence, EvidencePack):
        evidence = build_evidence_pack(final_state, tool_outputs=packed.get("tool_outputs"))

    return EvalBundle(
        ticker=ticker,
        section_id=section_id,
        final_state=final_state,
        child_runs=list(packed.get("child_runs") or []),
        evidence=evidence,
        fixture_meta=meta,
        source="langsmith",
        run_id=run_id,
    )
