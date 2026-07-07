"""Search memory for research subgraphs — records prior Perplexity searches."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.runtime.utils.context_compact import compact_if_needed
from tradingagents.equity_research.runtime.utils.llm_resolve import resolve_research_llm
from tradingagents.equity_research.state.consensus_schemas import EvidenceItem, SearchRecord

ANSWER_SUMMARY_THRESHOLD = 1500


def _llm_text(response: Any) -> str:
    return response.content if hasattr(response, "content") else str(response)


def _summarize_answer(deps: Any, answer: str, query: str) -> str:
    if len(answer) <= ANSWER_SUMMARY_THRESHOLD:
        return answer
    prompt = (
        "Summarize the following answer for an equity research agent in exactly 3-4 sentences of plain text. "
        "Do NOT output JSON. Use only plain prose.  "
        "Rules:  "
        "- Include key numbers/ranges that capture the breadth of estimates, but do NOT list all available numbers.  \n"
        "- End with a short takeaway that guides the user on what to trust, what to watch, or what source to use next.  \n"
        "- Keep every sentence under 40 words.  \n"
        "- Do not use bullet points or markdown.  \n\n"
        "- Summarize the content to be concise\n"
        "The answer below is to respond to the query:  \n"
        f"Query: {query}\n"
        "-----\n\n"
        "Answer:\n"
        f"{answer}"
    )
    return _llm_text(resolve_research_llm(deps, "nano").invoke(prompt))


def record_from_evidence(
    deps: Any,
    evidence: EvidenceItem,
    *,
    iteration: int,
    mode: str,
    query: str | None = None,
) -> SearchRecord:
    answer = evidence.answer or ""
    query = query or evidence.query_used or ""
    summary = _summarize_answer(deps, answer, query=query) if answer else ""
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
        # citations = record.get("citations") or []
        lines.append(f"Search (iteration {iteration}, dimension: {dim}, mode: {mode})")
        lines.append(f"Query: {query}")
        if answer:
            lines.append(f"Findings: {answer}")
        # if citations:
        #     lines.append("Citations:")
        #     for url in citations:
        #         lines.append(f"  - {url}")
    return "\n\n".join(lines)

def build_search_memory_for_prompt(
    deps: Any,
    records: list[dict],
    *,
    max_chars: int | None = None,
) -> str:
    formatted = format_search_memory(records)
    return compact_if_needed(deps, formatted, purpose="search memory", max_chars=max_chars)
