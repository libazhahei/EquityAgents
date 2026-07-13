"""Prompts for section research subgraph."""

from __future__ import annotations

import json
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.task_profile import TaskProfile
from tradingagents.equity_research.runtime.utils.context_compact import (
    assemble_and_compact_context,
)
from tradingagents.equity_research.runtime.utils.search_memory import (
    build_evidence_for_prompt,
)
from tradingagents.equity_research.state.consensus_schemas import get_consensus_view_for_prompt
from tradingagents.equity_research.tasks.section_research.schemas import (
    ResearchBrief,
    SectionResearchView,
)


def build_markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    """Build a markdown table from headers and rows."""
    header_row = "| " + " | ".join(headers) + " |"
    separator_row = "| " + " | ".join(["---"] * len(headers)) + " |"
    data_rows = ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join([header_row, separator_row] + data_rows) + "\n"


def get_assumption_context(brief: ResearchBrief) -> str:
    if not brief.assumption_view:
        return "{}"

    assumptions_map = build_markdown_table(
        headers=[
            "Consensus Anchor",
            "Assumption Statement",
            "Falsification Tests",
            "Model Drivers",
            "Next to Watch",
            "Priority",
        ],
        rows=[
            [
                a.get("consensus_anchor") or "N/A",
                a.get("assumption_statement"),
                ", ".join(a.get("falsification_tests", [])) if a.get("falsification_tests") else "",
                ", ".join(a.get("model_drivers", [])) if a.get("model_drivers") else "",
                ", ".join(a.get("next_to_watch", [])) if a.get("next_to_watch") else "",
                a.get("priority") or "",
            ]
            for a in brief.assumption_view["assumption_map"]
        ],
    )
    conflicts = build_markdown_table(
        headers=["Claim A", "Claim B", "Interpretation", "Status", "Next Check"],
        rows=[
            [
                c.get("claim_a") or "N/A",
                c.get("claim_b") or "N/A",
                c.get("interpretation") or "N/A",
                c.get("status") or "N/A",
                c.get("next_check") or "N/A",
            ]
            for c in brief.assumption_view["conflicts"]
        ],
    )
    top_research_priorities = brief.assumption_view.get("top_research_priorities", [])
    return (
        assumptions_map
        + "\n\n"
        + conflicts
        + "\n\n"
        + f"Top Research Priorities: \n- {'\n- '.join(top_research_priorities)}"
    )


def _raw_consensus_context(brief: ResearchBrief) -> str:
    if not brief.consensus_view:
        return "{}"
    if isinstance(brief.consensus_view, str):
        return brief.consensus_view
    return get_consensus_view_for_prompt({"consensus_view": brief.consensus_view})


def _format_questions_context(brief: ResearchBrief) -> str:
    if not brief.questions:
        return "[]"
    return build_markdown_table(
        headers=[
            "Question ID",
            "Parent Question ID",
            "Question Text",
            "Expected Output",
            "Suggested Sources",
            "Priority",
            "Required Evidence",
        ],
        rows=[
            [
                q.get("id") or "N/A",
                q.get("parent_id") or "N/A",
                q.get("question") or "",
                q.get("expected_output") or "",
                ", ".join(q.get("suggested_sources", [])) if q.get("suggested_sources") else "",
                q.get("priority") or "",
                ", ".join(q.get("required_evidence", [])) if q.get("required_evidence") else "",
            ]
            for q in brief.questions
        ],
    )


def _build_active_skills_block(deps: EquityResearchDeps, skills: dict[str, Any]) -> str:
    if not skills:
        return "{}"
    prompt_template = skills.get("prompt_template", "")
    query_guidance = skills.get("query_guidance", "")
    constraints = skills.get("constraints", "")
    return (
        f"Prompt Template: {prompt_template}\n"
        f"Query Guidance: {query_guidance}\n"
        f"Constraints: {constraints}\n"
    ).strip()


def build_initial_plan_prompt(deps: EquityResearchDeps, state: dict[str, Any]) -> str:
    brief = ResearchBrief.model_validate(state.get("research_brief") or {})
    skills = state.get("active_skill_context") or {}
    bfs_levels_data = state.get("bfs_levels") or []
    questions_block = _format_questions_context(brief)
    skills_block = _build_active_skills_block(deps, skills)
    prior_summaries = (state.get("parent_context") or {}).get("prior_session_summaries") or []
    prior_block = ""
    if prior_summaries:
        lines = []
        for s in prior_summaries[:5]:
            sid = s.get("section_id", "")
            summary = s.get("summary", "")
            lines.append(f"- Section {sid}: {summary}")
        prior_block = "\n".join(lines)

    context = assemble_and_compact_context(
        deps,
        {
            "Questions (from section planner)": questions_block,
            "BFS question waves": json.dumps(bfs_levels_data[:8]),
            "Consensus view (structured)": _raw_consensus_context(brief),
            "Assumption context": get_assumption_context(brief) if brief.assumption_view else "",
            "Active skills": skills_block,
            "Prior section research summaries": prior_block,
        },
        purpose="section research initial planner context",
    )
    return f"""
You are a senior equity research planner. Build a concise research plan for one report section.
    
Ticker: {state.get("ticker", "")}
Section: {brief.section_id} — {brief.section_title}
Root question: {brief.root_question}
Planning thesis: {brief.planning_thesis}
Required coverage outputs: {json.dumps(brief.coverage_outputs[:15])}
Data quality flags: {json.dumps(brief.data_quality_flags[:10])}

{context}

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
    context = assemble_and_compact_context(
        deps,
        {
            "Critical gaps": json.dumps(gaps[:10], indent=2),
            "Answer cards summary": json.dumps(answer_summary, indent=2),
        },
        purpose="section research replan context",
    )
    return f"""You are replanning section research based on coverage gaps or BFS wave advance.

Ticker: {state.get("ticker", "")}
Section: {state.get("section_id", "")}
Current plan version: {plan.get("version", 1)}
Current BFS wave index: {wave_index}
Next wave question ids (if advancing): {json.dumps(next_wave)}

{context}

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
    active = state.get("active_task") or {}
    parameter_grid = state.get("parameter_grid", "")
    context = assemble_and_compact_context(
        deps,
        {
            "Active task": json.dumps(active),
            "Parameter registry": parameter_grid or "",
            "Pending evidence": build_evidence_for_prompt(deps, pending, compact=False),
        },
        purpose="section research synthesizer context",
    )
    return f"""Synthesize pending evidence into section research view updates.

Ticker: {state.get("ticker", "")}
Section: {view.section_id}
Current answer cards: {list(view.answer_cards.keys())}

{context}

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
    todo_items_raw = todo.get("items") or []
    todo_summary_lines = []
    for item in todo_items_raw:
        if item.get("status") in ("pending", "in_progress"):
            todo_summary_lines.append(
                f"  - [{item.get('item_id')}] {item.get('title', '')}"
                f" | qid={item.get('question_id', '')}"
                f" | status={item.get('status')}"
            )
    todo_block = "\n".join(todo_summary_lines) if todo_summary_lines else "(none pending)"

    context = assemble_and_compact_context(
        deps,
        {
            "Coverage outputs required": json.dumps(
                (state.get("research_brief") or {}).get("coverage_outputs", [])[:12]
            ),
            "Answer cards": json.dumps(cards_payload, indent=2),
            "Todo items to double-check": todo_block,
            "Executor context (this iteration)": executor_context or "",
            "Search memory": memory_summary or "",
            "Parameter registry": state.get("parameter_grid", "") or "",
        },
        purpose="section research reflector context",
    )

    budget = iteration_budget or {}
    current_iter = budget.get("current", int(state.get("iterations", 0)))
    max_iter = budget.get("max", int(state.get("max_iterations", 0)))
    remaining = budget.get("remaining", max(0, max_iter - current_iter))
    pending_tasks = budget.get("pending_tasks", 0)
    pending_steps = budget.get("pending_steps", 0)
    pending_todo_items = budget.get("pending_todo_items", 0)
    question_iterations = budget.get("question_iterations", {})
    q_lines = []
    for qid, used in sorted(question_iterations.items()):
        q_rem = max(0, max_iter - used)
        q_lines.append(f"  {qid}: {used}/{max_iter} (remaining {q_rem})")
    q_block = "\n".join(q_lines) if q_lines else "  (no question iterations yet)"
    budget_block = (
        f"\n── Iteration Budget (per-question) ──\n"
        f"Max iterations per question: {max_iter}. "
        f"Global reflector passes: {current_iter}. "
        f"Min remaining across active questions: {remaining}.\n"
        f"Per-question usage:\n{q_block}\n"
        f"Pending plan: {pending_tasks} tasks, {pending_steps} steps. "
        f"Pending todo items: {pending_todo_items}.\n"
    )
    if remaining <= 0:
        budget_block += (
            "\u26a0 CRITICAL BUDGET: All active questions exhausted their iteration budget. "
            "You must recommend exit unless all required coverage outputs are already satisfied. "
            "Consolidate what you have.\n"
        )
    elif remaining <= 1:
        budget_block += (
            "\u26a0 CRITICAL BUDGET: At least one question has only 1 iteration left. "
            "You must recommend exit unless all required coverage outputs are already satisfied. "
            "Consolidate what you have.\n"
        )
    elif remaining <= 2:
        budget_block += (
            "\u26a0 LOW BUDGET: Prioritize finishing existing evidence over new research. "
            "Do NOT recommend plan_more. Recommend run_existing_queue or exit.\n"
        )

    return f"""Evaluate section research coverage and plan completion.

Ticker: {view.ticker}
Section: {view.section_id}
Research plan tasks: {len(plan.get("tasks", []))}

{context}
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
    context = assemble_and_compact_context(
        deps,
        {
            "Intent": str(brief.get("intent_hint", "")),
            "Answer cards": json.dumps({k: c.model_dump() for k, c in cards.items()}, indent=2),
            "Coverage": json.dumps(ctx.get("coverage") or {}, indent=2),
        },
        purpose="section research finalizer context",
    )
    return f"""Write the final section research report draft.

Ticker: {state.get("ticker", "")}
Section: {brief.get("section_title", "")} ({brief.get("section_id", "")})
Root question: {brief.get("root_question", "")}

{context}

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


def build_executor_system_prompt(state: dict[str, Any], action: str) -> str:
    synthesize_note = ""
    if "synthesize" in action.lower():
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
7. Always persist evidence and conclusions to memory before marking a todo item done.

── Tool Usage Guide ──

Todo Management: Use these tools to view, add, remove, or update research todo items. Each todo item is tied to a question_id and has a status (pending|in_progress|done|cancelled).
Memory Tools: Use these tools to store and retrieve evidence, claims, assumptions, and other structured data. Evidence should be stored with metadata (source_type, fiscal_quarter_or_date, platform, traceable_ref) for traceability.
Web Tools: Use these tools to find news, research reports, views, and data from external sources. Also use them to fetch filings, transcripts, and other primary sources. 
Filings & Official Docs: Use these tools to fetch and extract data from official filings, transcripts, and other primary sources. Always prefer primary sources when available.

Use these BEFORE re-fetching from external sources to avoid duplicate work.

── Typical Execution Flow ──

1. See what needs doing if current step and task is done and pick the next todo item
2. update_research_todo_status(item_id, "in_progress") → mark it as started.
3. Execute the step using search/fetch tools. You can use search tools to find filings, transcripts to retrieve primary sources.
4. store_evidence(fragment) → persist every piece of data found.
5. If drawing a conclusion: memory_write({{"type": "claim", ...}}) → record the conclusion.
6. If new work discovered: add_research_todo(...) → add follow-up items.
7. If item obsolete: remove_research_todo(item_id) or update_research_todo_status(item_id, "cancelled").
8. update_research_todo_status(item_id, "done") → mark complete.
9. Repeat from step 1 until no pending items remain.
If No pending research todo items found, then you may exit the execution. 
{synthesize_note}
Ticker: {state.get("ticker", "")}
Section: {state.get("section_id", "")}
"""
