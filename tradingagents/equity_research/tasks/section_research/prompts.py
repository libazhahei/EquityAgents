"""Prompts for section research subgraph."""

from __future__ import annotations

import json
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.context_compact import compact_prompt_block
from tradingagents.equity_research.runtime.utils.search_memory import build_search_memory_for_prompt, build_evidence_for_prompt
from tradingagents.equity_research.state.consensus_schemas import get_consensus_view_for_prompt
from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchBrief,
    SectionResearchView,
)


def _format_consensus_context(deps: EquityResearchDeps, brief: ResearchBrief) -> str:
    if not brief.consensus_view:
        return "{}"
    if isinstance(brief.consensus_view, str):
        raw = brief.consensus_view
    else:
        raw = get_consensus_view_for_prompt({"consensus_view": brief.consensus_view})
    return compact_prompt_block(deps, raw, purpose="consensus view for section planner")


def _format_assumption_context(deps: EquityResearchDeps, brief: ResearchBrief) -> str:
    if brief.assumption_report:
        raw = str(brief.assumption_report)
    elif brief.assumption_view:
        raw = json.dumps(brief.assumption_view, default=str)
    else:
        return "{}"
    return compact_prompt_block(deps, raw, purpose="assumption context for section planner")


def build_initial_plan_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    brief = ResearchBrief.model_validate(state.get("research_brief") or {})
    skills = state.get("active_skill_context") or {}
    bfs_levels_data = state.get("bfs_levels") or []
    questions_block = compact_prompt_block(
        deps,
        json.dumps(brief.questions[:12], indent=2),
        purpose="section planner questions",
    )
    skills_block = compact_prompt_block(
        deps,
        json.dumps(skills),
        purpose="active skills for section planner",
    )
    return f"""You are a senior equity research planner. Build a concise research plan for one report section.

Ticker: {state.get("ticker", "")}
Section: {brief.section_id} — {brief.section_title}
Root question: {brief.root_question}
Planning thesis: {brief.planning_thesis}
Required coverage outputs: {json.dumps(brief.coverage_outputs[:15])}
Data quality flags: {json.dumps(brief.data_quality_flags[:10])}

Questions (from section planner):
{questions_block}

BFS question waves (executor runs wave-by-wave): {json.dumps(bfs_levels_data[:8])}

Consensus view (structured):
{_format_consensus_context(deps, brief)}

Assumption context:
{_format_assumption_context(deps, brief)}

Active skills: {skills_block}

For each priority question in the current BFS wave, output a task with:
- task_id, question_id
- objective: what to learn (one clear goal)
- approach: rough how to research it (1-2 sentences, tools/sources)

Hard requirements (must be reflected through tasks tied to existing question_ids only):
- Enforce quant coverage on core conclusions: each core answer needs numeric support with metric, value/range, unit, and period.
- Enforce competition concreteness: include named threat-source validation tasks when related sub-questions exist.
- Enforce source metadata completeness: collect source_type, fiscal_quarter_or_date, platform, traceable_ref.
- Include a data-availability verification branch for any critical metric likely to be missing, with fallback proxy research.
- Do not introduce prior assumptions not implied by root/sub questions.

Return JSON matching SectionResearchPlanOutlineLLMOutput: plan_rationale, tasks, execution_order.
Prioritize priority=1 questions and those blocking coverage outputs.
Limit to at most 6 tasks. Do NOT list detailed steps — the system expands your outline."""


def build_replan_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    report = state.get("coverage_report") or {}
    plan = state.get("research_plan") or {}
    gaps = report.get("critical_gaps") or state.get("unresolved_gaps") or []
    wave_index = int(state.get("bfs_wave_index", 0))
    bfs_levels_data = state.get("bfs_levels") or []
    next_wave = bfs_levels_data[wave_index + 1] if wave_index + 1 < len(bfs_levels_data) else []
    answer_summary = {
        k: v.get("short_answer", "")
        for k, v in (state.get("answer_cards") or {}).items()
    }
    cards_block = compact_prompt_block(
        deps,
        json.dumps(answer_summary, indent=2),
        purpose="answer cards summary for replan",
    )
    gaps_block = compact_prompt_block(
        deps,
        json.dumps(gaps[:10], indent=2),
        purpose="critical gaps for replan",
    )
    return f"""You are replanning section research based on coverage gaps or BFS wave advance.

Ticker: {state.get("ticker", "")}
Section: {state.get("section_id", "")}
Current plan version: {plan.get("version", 1)}
Current BFS wave index: {wave_index}
Next wave question ids (if advancing): {json.dumps(next_wave)}

Critical gaps:
{gaps_block}

Answer cards summary:
{cards_block}

If wave-advance: add tasks only for next-wave questions (objective + approach each).
Otherwise add follow-up tasks ONLY for gaps. Do not replan completed work.
Do not add new assumptions outside root/sub-question scope.
When gaps are about missing numbers/sources/competition concreteness, prioritize tasks that:
- recover structured numeric evidence (metric, value/range, unit, period),
- recover structured source metadata (source_type, fiscal_quarter_or_date, platform, traceable_ref),
- validate data availability explicitly before concluding unavailable.
Return JSON matching SectionReplanLLMOutput: new_tasks (objective + approach only), append_steps, rationale."""


def build_synthesizer_prompt(
    deps: EquityResearchDeps,
    state: dict[str, Any],
    view: SectionResearchView,
    pending: list[dict],
) -> str:
    evidence_text = build_evidence_for_prompt(deps, pending, max_chars=8000)
    active = state.get("active_task") or {}
    active_block = compact_prompt_block(
        deps,
        json.dumps(active),
        purpose="active task for synthesizer",
    )
    # Inject parameter grid if available
    parameter_grid = state.get("parameter_grid", "")
    parameter_block = f"\n\n{parameter_grid}\n" if parameter_grid else ""
    return f"""Synthesize pending evidence into section research view updates.

Ticker: {state.get("ticker", "")}
Section: {view.section_id}
Active task: {active_block}
Current answer cards: {list(view.answer_cards.keys())}
{parameter_block}
Pending evidence:
{evidence_text}

Update answer_cards for relevant question_ids. Include verified_facts, calculations, citations, confidence.
Return SectionResearchViewUpdate JSON."""


def build_reflector_system_prompt(task_profile: TaskProfile) -> str:
    dimensions = ", ".join(task_profile.dimensions)
    return f"""You are a section research coverage evaluator for equity research.

Score coverage across dimensions: {dimensions}.

Rules:
- Assess plan_completion, question_scores, and critical_gaps.
- recommended_next_action must be exactly one of: run_existing_queue, plan_more, needs_human, exit.
- Use evidence quality and primary-source coverage when scoring.
- Flag contradictions and data quality issues explicitly.
    - Treat todo completion as a hard gate: if any todo item is still pending/in_progress,
      do NOT recommend exit. Recommend run_existing_queue (or plan_more only when queue is empty
      but unresolved coverage still requires new tasks).
    - Double-check todo items: if an item is still "pending" or "in_progress" but the corresponding
      answer card already has sufficient evidence (confidence >= 0.7 and non-empty verified_facts),
      list its item_id in completed_todo_ids. Only mark items that are genuinely finished.
    - Do NOT mark items as completed if the answer card has low confidence or missing primary evidence.

Iteration budget rules (critical — follow strictly):
- You will be told how many iterations remain out of the total budget.
- If remaining_iterations <= 1: set recommended_next_action to "exit" unless
  overall_score >= coverage_threshold and there are no critical gaps already met.
  Prioritize consolidating existing evidence over requesting more work.
- If remaining_iterations <= 2: do NOT recommend "plan_more"; only recommend
  "run_existing_queue" (to finish already-planned steps) or "exit".
- If remaining_iterations >= 3: normal evaluation rules apply.
Return structured JSON matching SectionCoverageEvaluation."""


def build_reflector_user_prompt(
    deps: EquityResearchDeps,
    view: SectionResearchView,
    memory_summary: str,
    state: dict[str, Any] | None = None,
    *,
    executor_context: str = "",
    iteration_budget: dict[str, int] | None = None,
) -> str:
    state = state or {}
    plan = state.get("research_plan") or {}
    todo = state.get("research_todo_list") or {}
    cards_payload = {
        k: {"confidence": v.confidence, "gaps": v.open_gaps}
        for k, v in view.answer_cards.items()
    }
    cards_block = compact_prompt_block(
        deps,
        json.dumps(cards_payload, indent=2),
        purpose="answer cards for reflector",
    )
    coverage_outputs = compact_prompt_block(
        deps,
        json.dumps((state.get("research_brief") or {}).get("coverage_outputs", [])[:12]),
        purpose="coverage outputs for reflector",
    )
    executor_block = ""
    if executor_context:
        executor_block = compact_prompt_block(
            deps,
            executor_context,
            purpose="executor context for reflector",
        )
    memory_block = memory_summary
    if memory_summary.strip():
        memory_block = compact_prompt_block(
            deps,
            memory_summary,
            purpose="search memory for reflector",
        )
    todo_items_raw = todo.get("items") or []
    todo_summary_lines = []
    for item in todo_items_raw:
        if item.get("status") in ("pending", "in_progress"):
            todo_summary_lines.append(
                f"  - [{item.get('item_id')}] {item.get('title', '')[:80]}"
                f" | qid={item.get('question_id', '')}"
                f" | status={item.get('status')}"
            )
    todo_block = "\n".join(todo_summary_lines) if todo_summary_lines else "(none pending)"

    # Inject parameter grid for the reflector's coverage assessment
    parameter_grid = state.get("parameter_grid", "")
    parameter_block = ""
    if parameter_grid:
        parameter_block = compact_prompt_block(
            deps,
            parameter_grid,
            purpose="parameter registry for reflector",
        )
    
    # Build budget block at the END to preserve prompt cache on static prefix
    budget = iteration_budget or {}
    current_iter = budget.get("current", int(state.get("iterations", 0)))
    max_iter = budget.get("max", int(state.get("max_iterations", 0)))
    remaining = budget.get("remaining", max(0, max_iter - current_iter))
    pending_tasks = budget.get("pending_tasks", 0)
    pending_steps = budget.get("pending_steps", 0)
    pending_todo_items = budget.get("pending_todo_items", 0)
    budget_block = (
        f"\n── Iteration Budget ──\n"
        f"Iteration budget: {current_iter}/{max_iter} completed, "
        f"{remaining} remaining. "
        f"Pending plan: {pending_tasks} tasks, {pending_steps} steps. "
        f"Pending todo items: {pending_todo_items}.\n"
    )
    if remaining <= 1:
        budget_block += (
            "\u26a0 CRITICAL BUDGET: You must recommend exit unless all required "
            "coverage outputs are already satisfied. Consolidate what you have.\n"
        )
    elif remaining <= 2:
        budget_block += (
            "\u26a0 LOW BUDGET: Prioritize finishing existing evidence over new research. "
            "Do NOT recommend plan_more. Recommend run_existing_queue or exit.\n"
        )
    
    # Static prefix first (for prompt cache), dynamic content after
    return f"""Evaluate section research coverage and plan completion.

Ticker: {view.ticker}
Section: {view.section_id}
Coverage outputs required: {coverage_outputs}
Answer cards: {cards_block}

Research plan tasks: {len(plan.get("tasks", []))}
Todo items to double-check (mark genuinely finished ones in completed_todo_ids):
{todo_block}

Executor context (this iteration):
{executor_block or "(none)"}

{memory_block}
Parameter registry:
{parameter_block or "(none)"}
{budget_block}"""


def build_reflector_prompt(
    deps: EquityResearchDeps,
    view: SectionResearchView,
    memory_summary: str,
    state: dict[str, Any] | None = None,
) -> str:
    """Legacy single-string prompt; prefer system + user split in reflector node."""
    from tradingagents.equity_research.tasks.section_research.profile import (
        SECTION_RESEARCH_TASK_PROFILE,
    )
    system = build_reflector_system_prompt(SECTION_RESEARCH_TASK_PROFILE)
    user = build_reflector_user_prompt(
        deps,
        view,
        memory_summary,
        state,
        executor_context=str((state or {}).get("executor_context_snapshot", "")),
    )
    return f"{system}\n\n{user}"


def build_finalizer_prompt(deps: EquityResearchDeps, ctx: dict[str, Any]) -> str:
    state = ctx.get("state") or {}
    view: SectionResearchView | None = ctx.get("view")
    brief = state.get("research_brief") or {}
    cards = view.answer_cards if view else {}
    intent_block = compact_prompt_block(
        deps,
        str(brief.get("intent_hint", "")),
        purpose="intent hint for finalizer",
    )
    cards_block = compact_prompt_block(
        deps,
        json.dumps({k: c.model_dump() for k, c in cards.items()}, indent=2),
        purpose="answer cards for finalizer",
    )
    coverage_block = compact_prompt_block(
        deps,
        json.dumps(ctx.get("coverage") or {}, indent=2),
        purpose="coverage for finalizer",
    )
    return f"""Write the final section research report draft.

Ticker: {state.get("ticker", "")}
Section: {brief.get("section_title", "")} ({brief.get("section_id", "")})
Root question: {brief.get("root_question", "")}
Intent: {intent_block}

Answer cards:
{cards_block}

Coverage: {coverage_block}

Produce professional equity research prose with citations. Max {ctx.get("report_max_chars", 6000)} chars.
Include executive summary at top.
If any required metric/source is unavailable after retries, add a dedicated disclosure section
that names missing datasets, attempted sources, and confidence impact."""


def build_skill_prompt(state: dict[str, Any], catalog_table: str, ticker: str) -> str:
    section_id = state.get("section_id", "")
    objective = state.get("research_objective", "section_research")
    return (
        f"Select skills for section research on {ticker}.\n"
        f"Section: {section_id}\n"
        f"Objective: {objective}\n"
        f"Sector: {state.get('sector', '')}\n\n"
        f"Skill catalog:\n{catalog_table}\n"
    )


def build_executor_system_prompt(state: dict[str, Any]) -> str:
    task = state.get("active_task") or {}
    step = state.get("active_step") or {}
    synthesize_note = ""
    if (step.get("action") or "").lower() == "synthesize":
        synthesize_note = (
            "\nNOTE: action=synthesize is handled by the downstream synthesizer node. "
            "Do not call tools for synthesize steps.\n"
        )
    return f"""You are an autonomous equity research executor.

Rules:
1. Start by calling list_research_todos(status="pending") to see the queue.
2. Execute the active step using appropriate tools (not search-only).
3. After completing a step, call update_research_todo_status(item_id, "done").
4. Use add_research_todo for newly discovered work; remove_research_todo for obsolete items.
5. Prefer primary sources (filings) over secondary when step action is fetch_primary or extract.
6. Do NOT call tools when active step action is synthesize — that step is handled downstream.
{synthesize_note}
Active task: {json.dumps(task)}
Active step: {json.dumps(step)}
Ticker: {state.get("ticker", "")}
Section: {state.get("section_id", "")}
Tool hints: {step.get("tool_hints", [])}
"""
