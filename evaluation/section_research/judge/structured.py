"""Default structured LLM judge (single call)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from evaluation.section_research.evaluators.faithfulness import summarize_evidence_for_prompt
from evaluation.section_research.judge.rubric import rubric_markdown_table
from evaluation.section_research.types import EvalBundle, JudgeBreakdown, RubricBreakdown
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.llm_clients import create_llm_client

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "judge_rubric.txt"


def _plan_coverage_summary(bundle: EvalBundle) -> str:
    state = bundle.final_state
    section_out = state.get("section_research_output") or {}
    plan = section_out.get("research_plan") or state.get("research_plan") or {}
    coverage = state.get("coverage_report") or {}
    todo = section_out.get("research_todo_list") or state.get("research_todo_list") or {}
    parts = [
        f"plan_tasks={len((plan or {}).get('tasks') or [])}",
        f"todo_items={len((todo or {}).get('items') or [])}",
        f"coverage_overall={coverage.get('overall_score', 'n/a')}",
        f"next_action={coverage.get('recommended_next_action', 'n/a')}",
        f"critical_gaps={coverage.get('critical_gaps', [])}",
        f"unresolved_gaps={section_out.get('unresolved_gaps') or []}",
        f"data_quality_notes={section_out.get('data_quality_notes') or []}",
    ]
    cards = section_out.get("answer_cards") or state.get("answer_cards") or {}
    if isinstance(cards, dict) and cards:
        parts.append("answer_card_ids=" + ", ".join(list(cards.keys())[:20]))
    return "\n".join(parts)


def _section_text(bundle: EvalBundle, *, max_chars: int = 12000) -> str:
    state = bundle.final_state
    section_out = state.get("section_research_output") or {}
    text = (
        section_out.get("final_section_text")
        or state.get("final_report")
        or section_out.get("executive_summary")
        or ""
    )
    text = text if isinstance(text, str) else str(text)
    if len(text) > max_chars:
        return text[:max_chars] + "\n…[truncated]"
    return text or "(empty section text)"


def build_judge_prompt(bundle: EvalBundle, rubric: RubricBreakdown) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")
    return (
        template.replace("{{RUBRIC_TABLE}}", rubric_markdown_table(rubric))
        .replace("{{TICKER}}", bundle.ticker)
        .replace("{{SECTION_ID}}", bundle.section_id)
        .replace(
            "{{REFERENCE_NOTES}}",
            bundle.fixture_meta.reference_notes or "(none)",
        )
        .replace("{{PLAN_COVERAGE_SUMMARY}}", _plan_coverage_summary(bundle))
        .replace(
            "{{EVIDENCE_SUMMARY}}",
            summarize_evidence_for_prompt(bundle.evidence),
        )
        .replace("{{SECTION_TEXT}}", _section_text(bundle))
    )


def _get_judge_llm(config: dict[str, Any] | None = None):
    cfg = config or DEFAULT_CONFIG.copy()
    client = create_llm_client(
        provider=cfg["llm_provider"],
        model=cfg.get("quick_think_llm") or cfg.get("nano_think_llm"),
        base_url=cfg.get("backend_url"),
    )
    return client.get_llm()


def run_structured_judge(
    bundle: EvalBundle,
    rubric: RubricBreakdown,
    *,
    config: dict[str, Any] | None = None,
    llm: Any | None = None,
) -> JudgeBreakdown:
    prompt = build_judge_prompt(bundle, rubric)
    model = llm or _get_judge_llm(config)
    structured = model.with_structured_output(JudgeBreakdown)
    result = structured.invoke(prompt)
    if isinstance(result, JudgeBreakdown):
        return result
    if isinstance(result, dict):
        return JudgeBreakdown.model_validate(result)
    # Some clients return message-like objects
    if hasattr(result, "model_dump"):
        return JudgeBreakdown.model_validate(result.model_dump())
    raise TypeError(f"Unexpected judge result type: {type(result)}")


def judge_breakdown_to_expected(judge: JudgeBreakdown) -> dict[str, float]:
    return {
        "content_quality": judge.content_quality,
        "coverage_vs_plan": judge.coverage_vs_plan,
        "faithfulness": judge.faithfulness,
        "gaps_honesty": judge.gaps_honesty,
        "overall": judge.overall,
        "faithfulness_score": judge.faithfulness,
        "judge_overall": judge.overall,
    }


def dump_prompt_debug(bundle: EvalBundle, rubric: RubricBreakdown, path: Path) -> None:
    path.write_text(
        json.dumps({"prompt": build_judge_prompt(bundle, rubric)}, indent=2),
        encoding="utf-8",
    )
