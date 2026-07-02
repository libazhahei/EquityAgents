"""Prompts for section research subgraph."""

from __future__ import annotations

import json
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.utils.search_memory import build_search_memory_for_prompt
from tradingagents.equity_research.state.consensus_schemas import get_consensus_view_for_prompt
from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchBrief,
    SectionResearchView,
)


def _format_consensus_context(brief: ResearchBrief) -> str:
    if not brief.consensus_view:
        return "{}"
    if isinstance(brief.consensus_view, str):
        return brief.consensus_view[:2000]
    return get_consensus_view_for_prompt({"consensus_view": brief.consensus_view})[:2000]


def _format_assumption_context(brief: ResearchBrief) -> str:
    if brief.assumption_report:
        return str(brief.assumption_report)[:2000]
    if brief.assumption_view:
        return str(brief.assumption_view)[:2000]
    return "{}"


def build_initial_plan_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    brief = ResearchBrief.model_validate(state.get("research_brief") or {})
    skills = state.get("active_skill_context") or {}
    bfs_levels_data = state.get("bfs_levels") or []
    return f"""You are a senior equity research planner. Build a multi-step research plan for one report section.

Ticker: {state.get("ticker", "")}
Section: {brief.section_id} — {brief.section_title}
Root question: {brief.root_question}
Planning thesis: {brief.planning_thesis}
Required coverage outputs: {json.dumps(brief.coverage_outputs[:15])}
Data quality flags: {json.dumps(brief.data_quality_flags[:10])}

Questions (from section planner):
{json.dumps(brief.questions[:12], indent=2)[:6000]}

BFS question waves (executor runs wave-by-wave): {json.dumps(bfs_levels_data[:8])}

Consensus view (structured):
{_format_consensus_context(brief)}

Assumption context (excerpt):
{_format_assumption_context(brief)}

Active skills: {json.dumps(skills)[:1500]}

For each question across ALL BFS waves, create a ResearchTask with ordered steps.
Each step must have: step_id, order, action (orient|search|fetch_primary|extract|calculate|compare|verify|synthesize),
description, tool_hints, expected_output.

Return JSON matching SectionResearchPlanLLMOutput schema with tasks and execution_order.
Prioritize questions with priority=1 and those blocking coverage outputs.
Limit to at most 8 tasks and 6 steps per task. The executor will run only the current BFS wave first."""


def build_replan_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    report = state.get("coverage_report") or {}
    plan = state.get("research_plan") or {}
    gaps = report.get("critical_gaps") or state.get("unresolved_gaps") or []
    wave_index = int(state.get("bfs_wave_index", 0))
    bfs_levels_data = state.get("bfs_levels") or []
    next_wave = bfs_levels_data[wave_index + 1] if wave_index + 1 < len(bfs_levels_data) else []
    return f"""You are replanning section research based on coverage gaps or BFS wave advance.

Ticker: {state.get("ticker", "")}
Section: {state.get("section_id", "")}
Current plan version: {plan.get("version", 1)}
Current BFS wave index: {wave_index}
Next wave question ids (if advancing): {json.dumps(next_wave)}

Critical gaps:
{json.dumps(gaps[:10], indent=2)}

Answer cards summary:
{json.dumps({k: v.get("short_answer", "")[:200] for k, v in (state.get("answer_cards") or {}).items()}, indent=2)[:3000]}

If this is a wave-advance replan, do not duplicate existing tasks; only ensure next-wave questions have tasks.
Otherwise add follow-up tasks or steps ONLY for the gaps. Do not replan completed work.
Return JSON matching SectionReplanLLMOutput: new_tasks, append_steps, new_todo_items, rationale."""


def build_synthesizer_prompt(
    deps: EquityResearchDeps,
    state: dict[str, Any],
    view: SectionResearchView,
    pending: list[dict],
) -> str:
    evidence_text = build_search_memory_for_prompt(deps, pending, max_chars=8000)
    active = state.get("active_task") or {}
    return f"""Synthesize pending evidence into section research view updates.

Ticker: {state.get("ticker", "")}
Section: {view.section_id}
Active task: {json.dumps(active)[:1000]}
Current answer cards: {list(view.answer_cards.keys())}

Pending evidence:
{evidence_text}

Update answer_cards for relevant question_ids. Include verified_facts, calculations, citations, confidence.
Return SectionResearchViewUpdate JSON."""


def build_reflector_prompt(
    deps: EquityResearchDeps,
    view: SectionResearchView,
    memory_summary: str,
    state: dict[str, Any] | None = None,
) -> str:
    state = state or {}
    plan = state.get("research_plan") or {}
    todo = state.get("research_todo_list") or {}
    return f"""Evaluate section research coverage and plan completion.

Ticker: {view.ticker}
Section: {view.section_id}
Coverage outputs required: {json.dumps((state.get("research_brief") or {}).get("coverage_outputs", [])[:12])}
Answer cards: {json.dumps({k: {"confidence": v.confidence, "gaps": v.open_gaps[:3]} for k, v in view.answer_cards.items()}, indent=2)[:3000]}

Research plan tasks: {len(plan.get("tasks", []))}
Todo items pending: {sum(1 for i in (todo.get("items") or []) if i.get("status") == "pending")}

{memory_summary}

Assess plan_completion, question_scores, critical_gaps.
recommended_next_action must be one of: run_existing_queue, plan_more, needs_human, exit.
Return SectionCoverageEvaluation JSON."""


def build_finalizer_prompt(deps: EquityResearchDeps, ctx: dict[str, Any]) -> str:
    state = ctx.get("state") or {}
    view: SectionResearchView | None = ctx.get("view")
    brief = state.get("research_brief") or {}
    cards = view.answer_cards if view else {}
    return f"""Write the final section research report draft.

Ticker: {state.get("ticker", "")}
Section: {brief.get("section_title", "")} ({brief.get("section_id", "")})
Root question: {brief.get("root_question", "")}
Intent: {str(brief.get("intent_hint", ""))[:1500]}

Answer cards:
{json.dumps({k: c.model_dump() for k, c in cards.items()}, indent=2)[:8000]}

Coverage: {json.dumps(ctx.get("coverage") or {}, indent=2)[:2000]}

Produce professional equity research prose with citations. Max {ctx.get("report_max_chars", 6000)} chars.
Include executive summary at top."""


def build_skill_prompt(skill_ctx: dict, objective: str, ticker: str) -> str:
    return f"Section research for {ticker}. Objective: {objective}. Skills: {json.dumps(skill_ctx)[:2000]}"


def build_executor_system_prompt(state: dict[str, Any]) -> str:
    task = state.get("active_task") or {}
    step = state.get("active_step") or {}
    return f"""You are an autonomous equity research executor.

Rules:
1. Start by calling list_research_todos(status="pending") to see the queue.
2. Execute the active step using appropriate tools (not search-only).
3. After completing a step, call update_research_todo_status(item_id, "done").
4. Use add_research_todo for newly discovered work; remove_research_todo for obsolete items.
5. Prefer primary sources (filings) over secondary when step action is fetch_primary or extract.

Active task: {json.dumps(task)[:1500]}
Active step: {json.dumps(step)[:1500]}
Ticker: {state.get("ticker", "")}
Section: {state.get("section_id", "")}
Tool hints: {step.get("tool_hints", [])}
"""
