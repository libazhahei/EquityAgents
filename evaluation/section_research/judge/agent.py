"""Optional light judge agent with read-only evidence tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from evaluation.section_research.judge.structured import build_judge_prompt, _get_judge_llm
from evaluation.section_research.types import EvalBundle, JudgeBreakdown, RubricBreakdown

logger = logging.getLogger(__name__)

_MAX_AGENT_STEPS = 6


def _make_tools(bundle: EvalBundle):
    evidence = bundle.evidence
    state = bundle.final_state

    @tool
    def list_evidence_ids() -> str:
        """List evidence_ledger entry ids / short claims."""
        rows = []
        for i, item in enumerate(evidence.evidence_ledger[:50]):
            if isinstance(item, dict):
                eid = item.get("evidence_id") or item.get("id") or i
                claim = item.get("claim") or item.get("text") or item.get("summary") or ""
                rows.append(f"{eid}: {str(claim)[:160]}")
            else:
                rows.append(f"{i}: {str(item)[:160]}")
        return "\n".join(rows) or "(empty evidence_ledger)"

    @tool
    def get_evidence_entry(evidence_id: str) -> str:
        """Fetch one evidence_ledger entry by evidence_id or index."""
        for i, item in enumerate(evidence.evidence_ledger):
            if not isinstance(item, dict):
                if str(i) == evidence_id:
                    return str(item)
                continue
            eid = str(item.get("evidence_id") or item.get("id") or i)
            if eid == evidence_id or str(i) == evidence_id:
                return json.dumps(item, default=str)[:4000]
        return f"evidence_id not found: {evidence_id}"

    @tool
    def list_citations() -> str:
        """List citation titles/urls available on the section output."""
        rows = []
        for i, cit in enumerate(evidence.citations[:40]):
            if isinstance(cit, dict):
                rows.append(
                    f"{i}: {cit.get('title') or ''} | {cit.get('url') or cit.get('source') or ''}"
                )
            else:
                rows.append(f"{i}: {cit}")
        return "\n".join(rows) or "(no citations)"

    @tool
    def list_tool_call_names() -> str:
        """List tool names observed in the trajectory / evidence pack."""
        names = []
        for toot in evidence.tool_outputs[:80]:
            names.append(str(toot.get("name") or "?"))
        for child in bundle.child_runs[:80]:
            if isinstance(child, dict):
                names.append(str(child.get("name") or "?"))
            else:
                names.append(str(getattr(child, "name", None) or "?"))
        # also research_traces
        for tr in (state.get("research_traces") or [])[:40]:
            if isinstance(tr, dict):
                names.append(str(tr.get("tool") or tr.get("name") or tr.get("node") or "?"))
        return "\n".join(f"- {n}" for n in names) or "(no tool calls)"

    @tool
    def get_coverage_report() -> str:
        """Return the coverage_report JSON (truncated)."""
        return json.dumps(state.get("coverage_report") or {}, default=str)[:4000]

    return [
        list_evidence_ids,
        get_evidence_entry,
        list_citations,
        list_tool_call_names,
        get_coverage_report,
    ]


def run_judge_agent(
    bundle: EvalBundle,
    rubric: RubricBreakdown,
    *,
    config: dict[str, Any] | None = None,
    llm: Any | None = None,
) -> JudgeBreakdown:
    """Tool-using judge that ends with structured JudgeBreakdown."""
    base_prompt = build_judge_prompt(bundle, rubric)
    tools = _make_tools(bundle)
    tool_map = {t.name: t for t in tools}
    model = llm or _get_judge_llm(config)
    bound = model.bind_tools(tools)

    messages: list[Any] = [
        SystemMessage(
            content=(
                "You are a section-research judge agent. Use read-only tools if needed to "
                "inspect evidence, then produce final scores. When ready to score, stop calling "
                "tools and reply with a short confirmation that you are ready to finalize."
            )
        ),
        HumanMessage(content=base_prompt + "\n\nYou may call tools before finalizing."),
    ]

    for step in range(_MAX_AGENT_STEPS):
        ai = bound.invoke(messages)
        messages.append(ai)
        tool_calls = getattr(ai, "tool_calls", None) or []
        if not tool_calls:
            break
        for tc in tool_calls:
            name = tc.get("name")
            args = tc.get("args") or {}
            call_id = tc.get("id") or name
            tool = tool_map.get(name)
            if tool is None:
                content = f"unknown tool: {name}"
            else:
                try:
                    content = tool.invoke(args)
                except Exception as exc:  # noqa: BLE001 — surface to agent
                    content = f"tool error: {exc}"
            messages.append(ToolMessage(content=str(content)[:6000], tool_call_id=call_id))
        logger.info("judge-agent step=%s tool_calls=%s", step, [t.get("name") for t in tool_calls])

    structured = model.with_structured_output(JudgeBreakdown)
    final_prompt = (
        base_prompt
        + "\n\n## Agent investigation notes\n"
        + "Use any tool findings already gathered. Output the structured score breakdown now."
    )
    # Include last few messages as context (truncated)
    transcript = []
    for m in messages[-8:]:
        role = getattr(m, "type", m.__class__.__name__)
        content = getattr(m, "content", "")
        transcript.append(f"[{role}] {str(content)[:800]}")
    final_prompt += "\n\n### Recent agent transcript\n" + "\n".join(transcript)

    result = structured.invoke(final_prompt)
    if isinstance(result, JudgeBreakdown):
        return result
    if isinstance(result, dict):
        return JudgeBreakdown.model_validate(result)
    if hasattr(result, "model_dump"):
        return JudgeBreakdown.model_validate(result.model_dump())
    raise TypeError(f"Unexpected judge agent result type: {type(result)}")
