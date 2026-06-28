"""Search memory for consensus subgraph — records prior Perplexity searches."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.agents.consensus.context_compact import compact_if_needed
from tradingagents.equity_research.state.consensus_schemas import EvidenceItem, SearchRecord

ANSWER_SUMMARY_THRESHOLD = 1500


def _llm_text(response: Any) -> str:
    return response.content if hasattr(response, "content") else str(response)


def _summarize_answer(deps: Any, answer: str) -> str:
    if len(answer) <= ANSWER_SUMMARY_THRESHOLD:
        return answer
    prompt = (
        "Summarize the following search answer in 1-3 sentences for an equity research agent.\n"
        "Keep key numbers and facts. Use plain prose, not JSON.\n\n"
        f"{answer}"
    )
    return _llm_text(deps.quick_llm.invoke(prompt))


def record_from_evidence(
    deps: Any,
    evidence: EvidenceItem,
    *,
    iteration: int,
    mode: str,
) -> SearchRecord:
    answer = evidence.answer or ""
    summary = _summarize_answer(deps, answer) if answer else ""
    return SearchRecord(
        record_id=f"sr_{uuid.uuid4().hex[:8]}",
        iteration=iteration,
        query=evidence.query_used,
        target_dimension=evidence.target_dimension,
        mode=mode,
        answer=answer,
        answer_summary=summary,
        citations=list(evidence.citations),
        doc_ids=list(evidence.doc_ids),
        retrieved_at=evidence.retrieved_at,
    )


def append_search_record(
    memory: list[dict],
    record: SearchRecord,
) -> list[dict]:
    updated = list(memory)
    updated.append(record.model_dump())
    return updated


def queries_from_memory(records: list[dict]) -> list[str]:
    return [str(r.get("query", "")) for r in records if r.get("query")]


def format_search_memory(records: list[dict], *, max_records: int = 20) -> str:
    if not records:
        return "- No prior searches recorded."
    lines: list[str] = []
    for record in records[-max_records:]:
        dim = record.get("target_dimension", "")
        query = record.get("query", "")
        mode = record.get("mode", "")
        iteration = record.get("iteration", 0)
        answer = record.get("answer_summary") or record.get("answer", "")
        citations = record.get("citations") or []
        lines.append(f"- Search (iteration {iteration}, dimension: {dim}, mode: {mode})")
        lines.append(f"  - Query: {query}")
        if answer:
            lines.append(f"  - Findings: {answer[:800]}")
        if citations:
            lines.append("  - Citations:")
            for url in citations:
                lines.append(f"    - {url}")
    return "\n".join(lines)


def build_search_memory_for_prompt(
    deps: Any,
    records: list[dict],
    *,
    max_chars: int | None = None,
) -> str:
    formatted = format_search_memory(records)
    return compact_if_needed(deps, formatted, purpose="search memory", max_chars=max_chars)
