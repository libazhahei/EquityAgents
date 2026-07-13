#!/usr/bin/env python3
"""Coarse audit of session blackboard usefulness within one section dump.

Metrics (A+B):
  - entry type / source_node distribution
  - near-dup rate vs P3 corpus (evidence-like + report + coverage + structured views)
  - coarse uptake of non-near-dup entries into U2 (plan / todo)
  - injection cost estimate (chars of top-N injected slice; waste from near-dups)

Default verdict thresholds (overridable via flags):
  near_dup > 0.70 AND non_finding_share < 0.10 AND uptake ≈ 0
  → efficacy_suspect (skip instrumentation for now)

Usage:
  uv run python scripts/audit_blackboard_section.py out/nvda_section3.json
  uv run python scripts/audit_blackboard_section.py out/nvda_section3.json --json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from tradingagents.equity_research.memory.similarity import text_similarity
from tradingagents.equity_research.state.blackboard import format_blackboard_for_prompt

# Keep aligned with blackboard_reducer near-dup threshold.
_DEFAULT_SIM = 0.85
_DEFAULT_MAX_ITEMS = 8  # planner injection; executor uses 6


def _walk_strings(obj: Any, *, min_len: int = 20, out: list[str] | None = None) -> list[str]:
    """Collect substantive strings from nested JSON-like structures."""
    if out is None:
        out = []
    if isinstance(obj, str):
        s = obj.strip()
        if len(s) >= min_len:
            out.append(s)
    elif isinstance(obj, dict):
        for v in obj.values():
            _walk_strings(v, min_len=min_len, out=out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_strings(v, min_len=min_len, out=out)
    return out


def _chunk_long_text(text: str, *, window: int = 400, step: int = 200) -> list[str]:
    """Split long docs so Jaccard vs short blackboard snippets is meaningful."""
    s = (text or "").strip()
    if not s:
        return []
    if len(s) <= window:
        return [s]
    # Prefer paragraph-ish splits, then window leftovers.
    parts = [p.strip() for p in s.replace("\r\n", "\n").split("\n\n") if len(p.strip()) >= 20]
    chunks: list[str] = []
    for p in parts:
        if len(p) <= window * 2:
            chunks.append(p)
        else:
            for i in range(0, len(p), step):
                piece = p[i : i + window]
                if len(piece.strip()) >= 20:
                    chunks.append(piece)
                if i + window >= len(p):
                    break
    if not chunks:
        for i in range(0, len(s), step):
            piece = s[i : i + window]
            if len(piece.strip()) >= 20:
                chunks.append(piece)
            if i + window >= len(s):
                break
    return chunks


def _expand_corpus(strings: list[str]) -> list[str]:
    expanded: list[str] = []
    for s in strings:
        if len(s) > 600:
            expanded.extend(_chunk_long_text(s))
        else:
            expanded.append(s)
    return expanded


def _token_coverage(query: str, corpus_text: str) -> float:
    """Asymmetric query→corpus token coverage (secondary signal)."""
    if not query or not corpus_text:
        return 0.0
    q_tokens = set(query.lower().split())
    t_tokens = set(corpus_text.lower().split())
    if not q_tokens:
        return 0.0
    return len(q_tokens & t_tokens) / len(q_tokens)


def _load_dump(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return data


def _resolve_section_id(data: dict[str, Any], section_id: str | None) -> str:
    boards = data.get("session_blackboards") or {}
    if section_id:
        if section_id not in boards:
            raise SystemExit(f"section_id={section_id!r} not in session_blackboards keys={list(boards)}")
        return section_id
    if isinstance(boards, dict) and boards:
        if len(boards) == 1:
            return next(iter(boards))
        preferred = data.get("section_id") or data.get("active_section_id")
        if preferred in boards:
            return str(preferred)
        raise SystemExit(f"Multiple sections in session_blackboards; pass --section-id. keys={list(boards)}")
    raise SystemExit("No session_blackboards entries found in dump")


def _blackboard_entries(data: dict[str, Any], section_id: str) -> list[dict[str, Any]]:
    raw = (data.get("session_blackboards") or {}).get(section_id) or []
    return [e for e in raw if isinstance(e, dict) and str(e.get("content") or "").strip()]


def _section_output(data: dict[str, Any], section_id: str) -> dict[str, Any]:
    outputs = data.get("section_research_outputs") or {}
    if isinstance(outputs, dict) and section_id in outputs and isinstance(outputs[section_id], dict):
        return outputs[section_id]
    single = data.get("section_research_output")
    if isinstance(single, dict) and (not single.get("section_id") or single.get("section_id") == section_id):
        return single
    return {}


def _build_p3_corpus(data: dict[str, Any], section_id: str) -> dict[str, list[str]]:
    """P3: evidence-like + final report/articles + coverage/structured view text."""
    buckets: dict[str, list[str]] = {
        "answer_cards": [],
        "final_report": [],
        "coverage_report": [],
        "ledgers": [],
        "trace_evidence_like": [],
        "structured_misc": [],
    }

    cards = data.get("answer_cards") or {}
    sro = _section_output(data, section_id)
    if not cards and isinstance(sro.get("answer_cards"), dict):
        cards = sro["answer_cards"]
    buckets["answer_cards"] = _walk_strings(cards)

    report = data.get("final_report") or sro.get("final_section_text") or sro.get("executive_summary") or ""
    if report:
        buckets["final_report"] = _chunk_long_text(str(report))

    buckets["coverage_report"] = _expand_corpus(
        _walk_strings(data.get("coverage_report") or sro.get("coverage_report") or {})
    )

    for key in ("consensus_ledger", "assumption_ledger"):
        buckets["ledgers"].extend(_expand_corpus(_walk_strings(data.get(key) or [])))

    # Traces often store counts only; still harvest any embedded text.
    for trace in data.get("research_traces") or []:
        if not isinstance(trace, dict):
            continue
        if trace.get("section_id") and trace.get("section_id") != section_id:
            continue
        payload = trace.get("payload") or {}
        name = str(trace.get("node_name") or "")
        if any(x in name for x in ("executor", "synthesizer", "reflector")):
            buckets["trace_evidence_like"].extend(_expand_corpus(_walk_strings(payload)))

    for key in ("parameter_grid", "parameter_registry", "iteration_snapshots"):
        buckets["structured_misc"].extend(_expand_corpus(_walk_strings(data.get(key) or {})))

    buckets["answer_cards"] = _expand_corpus(buckets["answer_cards"])
    return buckets


def _build_u2_corpus(data: dict[str, Any], section_id: str) -> dict[str, list[str]]:
    """U2: plan / todo final state + planner-ish trace payloads."""
    buckets: dict[str, list[str]] = {
        "research_plan": [],
        "research_todo_list": [],
        "planner_traces": [],
    }
    sro = _section_output(data, section_id)
    plan = data.get("research_plan") or sro.get("research_plan") or {}
    todo = data.get("research_todo_list") or sro.get("research_todo_list") or {}
    buckets["research_plan"] = _expand_corpus(_walk_strings(plan))
    buckets["research_todo_list"] = _expand_corpus(_walk_strings(todo))

    for trace in data.get("research_traces") or []:
        if not isinstance(trace, dict):
            continue
        if trace.get("section_id") and trace.get("section_id") != section_id:
            continue
        name = str(trace.get("node_name") or "")
        if "planner" in name:
            buckets["planner_traces"].extend(_expand_corpus(_walk_strings(trace.get("payload") or {})))
    return buckets


def _flatten(buckets: dict[str, list[str]]) -> list[str]:
    out: list[str] = []
    for items in buckets.values():
        out.extend(items)
    return out


def _max_sim(text: str, corpus: list[str]) -> float:
    if not text or not corpus:
        return 0.0
    best = 0.0
    for other in corpus:
        if other is text or other == text:
            continue
        s = text_similarity(text, other)
        if s > best:
            best = s
            if best >= 0.999:
                break
    return best


def _estimate_tokens(chars: int) -> int:
    # Rough English/code-mix heuristic used only for relative cost.
    return max(0, (chars + 3) // 4)


def _todo_items(data: dict[str, Any], section_id: str) -> list[dict[str, Any]]:
    todo = data.get("research_todo_list") or {}
    sro = _section_output(data, section_id)
    if not todo and isinstance(sro.get("research_todo_list"), dict):
        todo = sro["research_todo_list"]
    items = todo.get("items") if isinstance(todo, dict) else None
    if not isinstance(items, list):
        return []
    return [i for i in items if isinstance(i, dict)]


def _structural_uptake(
    entries: list[dict[str, Any]],
    todo_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Measure BB→todo linkage via blackboard_entry_id (honest structured uptake)."""
    bb_ids = {str(e.get("entry_id")) for e in entries if e.get("entry_id")}
    materializable_n = sum(
        1 for e in entries if str(e.get("entry_type") or "") in {"methodology", "contradiction"}
    )

    linked_todos = [
        i for i in todo_items
        if i.get("blackboard_entry_id") and str(i.get("blackboard_entry_id")) in bb_ids
    ]
    linked_ids = {str(i.get("blackboard_entry_id")) for i in linked_todos}
    linked_pending = [i for i in linked_todos if i.get("status") in ("pending", "in_progress")]
    linked_done = [i for i in linked_todos if i.get("status") == "done"]
    reflector_without_id = [
        i for i in todo_items
        if str(i.get("source") or "") == "reflector" and not i.get("blackboard_entry_id")
    ]

    linked_n = len(linked_todos)
    done_n = len(linked_done)
    pending_n = len(linked_pending)
    link_rate = (len(linked_ids) / materializable_n) if materializable_n else 0.0
    done_rate = (done_n / linked_n) if linked_n else 0.0

    return {
        "materializable_entry_count": materializable_n,
        "structural_linked": linked_n,
        "structural_linked_unique_entries": len(linked_ids),
        "structural_done": done_n,
        "structural_pending": pending_n,
        "structural_done_rate": round(done_rate, 4),
        "link_rate": round(link_rate, 4),
        "reflector_source_without_entry_id": len(reflector_without_id),
        "linked_todo_previews": [
            {
                "item_id": i.get("item_id"),
                "status": i.get("status"),
                "action": i.get("action"),
                "blackboard_entry_id": i.get("blackboard_entry_id"),
                "title": str(i.get("title") or "")[:120],
            }
            for i in linked_todos[:8]
        ],
    }


def audit_dump(
    data: dict[str, Any],
    *,
    section_id: str,
    similarity: float = _DEFAULT_SIM,
    max_items: int = _DEFAULT_MAX_ITEMS,
    near_dup_threshold: float = 0.70,
    non_finding_threshold: float = 0.10,
) -> dict[str, Any]:
    entries = _blackboard_entries(data, section_id)
    p3_buckets = _build_p3_corpus(data, section_id)
    u2_buckets = _build_u2_corpus(data, section_id)
    p3 = _flatten(p3_buckets)
    u2 = _flatten(u2_buckets)
    p3_joined = "\n".join(p3)
    u2_joined = "\n".join(u2)

    type_counts = Counter(str(e.get("entry_type") or "unknown") for e in entries)
    source_counts = Counter(str(e.get("source_node") or "unknown") for e in entries)
    n = len(entries)
    non_finding = n - type_counts.get("finding", 0)
    non_finding_share = (non_finding / n) if n else 0.0

    per_entry: list[dict[str, Any]] = []
    near_dup_n = 0
    covered_n = 0
    novel_n = 0
    uptake_n = 0
    uptake_covered_n = 0
    internal_dup_n = 0

    bb_texts = [str(e.get("content") or "") for e in entries]
    # Secondary threshold: most BB tokens already appear somewhere in P3 pool.
    coverage_threshold = min(0.70, similarity)

    for i, entry in enumerate(entries):
        content = bb_texts[i]
        p3_sim = _max_sim(content, p3)
        p3_coverage = _token_coverage(content, p3_joined)
        # Internal near-dup: earlier entries only (first-seen wins, like reducer).
        internal_sim = _max_sim(content, bb_texts[:i]) if i else 0.0
        is_near_dup = p3_sim >= similarity
        is_covered = p3_coverage >= coverage_threshold
        is_internal_dup = internal_sim >= similarity
        if is_near_dup:
            near_dup_n += 1
        if is_covered:
            covered_n += 1
        if is_internal_dup:
            internal_dup_n += 1

        u2_sim = _max_sim(content, u2)
        u2_coverage = _token_coverage(content, u2_joined)
        # Novel = not Jaccard-near-dup against a P3 chunk (primary agreed metric).
        is_novel = not is_near_dup
        taken_up = False
        taken_up_soft = False
        if is_novel:
            novel_n += 1
            taken_up = u2_sim >= similarity
            taken_up_soft = u2_coverage >= coverage_threshold
            if taken_up:
                uptake_n += 1
            if taken_up_soft:
                uptake_covered_n += 1

        per_entry.append(
            {
                "entry_id": entry.get("entry_id"),
                "entry_type": entry.get("entry_type"),
                "source_node": entry.get("source_node"),
                "created_at_iteration": entry.get("created_at_iteration"),
                "content_preview": content[:160],
                "p3_similarity": round(p3_sim, 4),
                "p3_token_coverage": round(p3_coverage, 4),
                "internal_similarity": round(internal_sim, 4),
                "u2_similarity": round(u2_sim, 4),
                "u2_token_coverage": round(u2_coverage, 4),
                "near_dup_p3": is_near_dup,
                "covered_by_p3": is_covered,
                "internal_dup": is_internal_dup,
                "novel": is_novel,
                "uptake_u2": taken_up,
                "uptake_u2_soft": taken_up_soft,
            }
        )

    near_dup_rate = (near_dup_n / n) if n else 0.0
    covered_rate = (covered_n / n) if n else 0.0
    internal_dup_rate = (internal_dup_n / n) if n else 0.0
    uptake_rate_among_novel = (uptake_n / novel_n) if novel_n else 0.0
    soft_uptake_rate_among_novel = (uptake_covered_n / novel_n) if novel_n else 0.0

    # Cost: chars that would be injected (top max_items by format_blackboard sort).
    injected_text = format_blackboard_for_prompt(entries, max_items=max_items, section_id=section_id)
    injected_chars = len(injected_text)
    # Among the same top-N slice, how many are P3 near-dups / covered.
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.get("created_at_iteration", 0), e.get("created_at", "")),
        reverse=True,
    )[:max_items]
    injected_dup_n = 0
    injected_covered_n = 0
    for e in sorted_entries:
        content = str(e.get("content") or "")
        if _max_sim(content, p3) >= similarity:
            injected_dup_n += 1
        if _token_coverage(content, p3_joined) >= coverage_threshold:
            injected_covered_n += 1
    injected_waste_share = (injected_dup_n / len(sorted_entries)) if sorted_entries else 0.0
    injected_covered_share = (injected_covered_n / len(sorted_entries)) if sorted_entries else 0.0

    report_chars = len(str(data.get("final_report") or _section_output(data, section_id).get("final_section_text") or ""))
    prompt_share_vs_report = (injected_chars / report_chars) if report_chars else None

    p3_pool_chars = sum(len(s) for s in p3)
    limitations = []
    if not p3_buckets["trace_evidence_like"] or all(
        not str(x).strip() or str(x).isdigit() or len(str(x)) < 40 for x in p3_buckets["trace_evidence_like"]
    ):
        limitations.append(
            "research_traces mostly lack evidence snippet text (counts/ids only); "
            "near-dup is mainly vs answer_cards/final_report/coverage/ledgers."
        )
    if not u2_buckets["planner_traces"] or sum(len(s) for s in u2_buckets["planner_traces"]) < 80:
        limitations.append(
            "planner trace payloads are sparse; text uptake leans on final research_plan / "
            "research_todo_list. Prefer structural_* metrics when blackboard_entry_id is present."
        )

    structural = _structural_uptake(entries, _todo_items(data, section_id))

    # Primary verdict uses agreed Jaccard near-dup; also flag synthesizer-only
    # echo boards that never appear in plan/todo (common when BB stores raw tables
    # that neither Jaccard-match narrative chunks nor influence planning).
    echo_without_uptake = bool(
        n > 0
        and non_finding_share < non_finding_threshold
        and source_counts.get("synthesizer", 0) / n >= 0.9
        and uptake_n == 0
        and uptake_covered_n == 0
        and structural["structural_linked"] == 0
    )
    efficacy_suspect = bool(
        n > 0
        and structural["structural_linked"] == 0
        and non_finding_share < non_finding_threshold
        and uptake_n == 0
        and uptake_covered_n == 0
        and (
            near_dup_rate > near_dup_threshold
            or (covered_rate > near_dup_threshold and near_dup_rate < 0.15)
            or echo_without_uptake
        )
    )

    if n == 0:
        verdict = "no_data"
        verdict_detail = "No blackboard entries for this section."
    elif structural["structural_linked"] > 0 and structural["structural_done"] > 0:
        verdict = "structural_uptake_ok"
        verdict_detail = (
            f"structural_linked={structural['structural_linked']} "
            f"(unique entries {structural['structural_linked_unique_entries']}), "
            f"done={structural['structural_done']}, pending={structural['structural_pending']}, "
            f"link_rate={structural['link_rate']:.0%} of methodology/contradiction entries."
        )
    elif structural["structural_linked"] > 0 and structural["structural_pending"] > 0:
        verdict = "materialized_but_unexecuted"
        verdict_detail = (
            f"BB→todo linked={structural['structural_linked']} but none done "
            f"(pending/in_progress={structural['structural_pending']}). "
            f"link_rate={structural['link_rate']:.0%}. "
            f"Fix routing/exit so linked todos run before exit."
        )
    elif structural["structural_linked"] > 0:
        # Linked but neither pending nor done (e.g. cancelled only)
        verdict = "structural_linked_inactive"
        verdict_detail = (
            f"structural_linked={structural['structural_linked']} but no pending/done items "
            f"(check cancelled/other statuses)."
        )
    elif efficacy_suspect:
        verdict = "efficacy_suspect"
        if echo_without_uptake and near_dup_rate <= near_dup_threshold and covered_rate <= near_dup_threshold:
            verdict_detail = (
                f"synthesizer-only findings ({source_counts.get('synthesizer', 0)}/{n}), "
                f"non_finding_share={non_finding_share:.0%}, "
                f"near_dup={near_dup_rate:.0%}/covered={covered_rate:.0%} "
                f"(low match to final artifacts), "
                f"novel_uptake={uptake_n} (soft={uptake_covered_n}). "
                f"Looks like unused evidence echo — skip instrumentation for now."
            )
        else:
            verdict_detail = (
                f"near_dup_rate={near_dup_rate:.0%}, covered_rate={covered_rate:.0%} "
                f"(threshold {near_dup_threshold:.0%}), "
                f"non_finding_share={non_finding_share:.0%} < {non_finding_threshold:.0%}, "
                f"novel_uptake={uptake_n} (soft={uptake_covered_n}). Skip instrumentation for now."
            )
    else:
        verdict = "needs_instrumentation_or_broader_sample"
        verdict_detail = (
            "No blackboard_entry_id linkage and coarse text signals are mixed; "
            "consider prompt-injection logging and/or more dumps before concluding."
        )

    return {
        "section_id": section_id,
        "entry_count": n,
        "type_counts": dict(type_counts),
        "source_counts": dict(source_counts),
        "non_finding_share": round(non_finding_share, 4),
        "similarity_threshold": similarity,
        "coverage_threshold": coverage_threshold,
        "near_dup_rate_vs_p3": round(near_dup_rate, 4),
        "token_coverage_rate_vs_p3": round(covered_rate, 4),
        "internal_near_dup_rate": round(internal_dup_rate, 4),
        "novel_count": novel_n,
        "uptake_count_among_novel": uptake_n,
        "uptake_rate_among_novel": round(uptake_rate_among_novel, 4),
        "soft_uptake_count_among_novel": uptake_covered_n,
        "soft_uptake_rate_among_novel": round(soft_uptake_rate_among_novel, 4),
        "structural": structural,
        "cost": {
            "max_items_injected": max_items,
            "injected_chars": injected_chars,
            "injected_tokens_est": _estimate_tokens(injected_chars),
            "injected_near_dup_count": injected_dup_n,
            "injected_waste_share": round(injected_waste_share, 4),
            "injected_covered_count": injected_covered_n,
            "injected_covered_share": round(injected_covered_share, 4),
            "final_report_chars": report_chars,
            "injected_chars_over_final_report": (
                round(prompt_share_vs_report, 4) if prompt_share_vs_report is not None else None
            ),
            "p3_pool_chars": p3_pool_chars,
            "p3_bucket_sizes": {k: len(v) for k, v in p3_buckets.items()},
            "u2_bucket_sizes": {k: len(v) for k, v in u2_buckets.items()},
        },
        "verdict": verdict,
        "verdict_detail": verdict_detail,
        "efficacy_suspect": efficacy_suspect,
        "limitations": limitations,
        "entries": per_entry,
    }


def _print_human(report: dict[str, Any]) -> None:
    cost = report["cost"]
    print(f"section_id: {report['section_id']}")
    print(f"entries: {report['entry_count']}")
    print(f"types: {report['type_counts']}")
    print(f"sources: {report['source_counts']}")
    print(f"non_finding_share: {report['non_finding_share']:.1%}")
    print(
        f"near_dup_vs_P3 (@{report['similarity_threshold']} Jaccard): "
        f"{report['near_dup_rate_vs_p3']:.1%}"
    )
    print(
        f"token_coverage_vs_P3 (@{report['coverage_threshold']}): "
        f"{report['token_coverage_rate_vs_p3']:.1%}"
    )
    print(f"internal_near_dup: {report['internal_near_dup_rate']:.1%}")
    print(
        f"novel: {report['novel_count']} | "
        f"uptake_into_U2: {report['uptake_count_among_novel']} "
        f"({report['uptake_rate_among_novel']:.1%} of novel); "
        f"soft_uptake: {report['soft_uptake_count_among_novel']} "
        f"({report['soft_uptake_rate_among_novel']:.1%})"
    )
    structural = report.get("structural") or {}
    if structural:
        print(
            f"structural: linked={structural.get('structural_linked', 0)} "
            f"(unique={structural.get('structural_linked_unique_entries', 0)}, "
            f"link_rate={structural.get('link_rate', 0):.1%} of "
            f"{structural.get('materializable_entry_count', 0)} methodology/contradiction); "
            f"done={structural.get('structural_done', 0)} "
            f"pending={structural.get('structural_pending', 0)}; "
            f"reflector_source_without_entry_id="
            f"{structural.get('reflector_source_without_entry_id', 0)}"
        )
        previews = structural.get("linked_todo_previews") or []
        if previews:
            print("structural linked todos:")
            for item in previews[:5]:
                print(
                    f"  [{item.get('status')}/{item.get('action')}] "
                    f"{item.get('blackboard_entry_id')} {item.get('title')!r}"
                )
    print(
        f"cost: inject~{cost['injected_chars']} chars "
        f"(~{cost['injected_tokens_est']} tok, top {cost['max_items_injected']}); "
        f"injected_waste_share={cost['injected_waste_share']:.1%}; "
        f"injected_covered_share={cost['injected_covered_share']:.1%}; "
        f"vs final_report={cost['injected_chars_over_final_report']}"
    )
    print(f"verdict: {report['verdict']}")
    print(f"detail: {report['verdict_detail']}")
    if report["limitations"]:
        print("limitations:")
        for line in report["limitations"]:
            print(f"  - {line}")

    # Show a few novel / near-dup examples
    novel = [e for e in report["entries"] if e["novel"]][:3]
    dups = [e for e in report["entries"] if e["near_dup_p3"]][:3]
    if dups:
        print("\nnear-dup examples:")
        for e in dups:
            print(f"  [{e['entry_type']}/{e['source_node']}] p3={e['p3_similarity']:.2f} {e['content_preview']!r}")
    if novel:
        print("\nnovel examples (and uptake flag):")
        for e in novel:
            print(
                f"  [{e['entry_type']}/{e['source_node']}] "
                f"p3_cov={e['p3_token_coverage']:.2f} u2={e['u2_similarity']:.2f} "
                f"uptake={e['uptake_u2']}/{e['uptake_u2_soft']} {e['content_preview']!r}"
            )
    elif report["entry_count"]:
        print("\n(no novel entries vs P3 under current threshold)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Coarse-audit session blackboard in a section dump.")
    parser.add_argument(
        "dump",
        nargs="?",
        default="out/nvda_section3.json",
        help="Path to section/e2e JSON dump (default: out/nvda_section3.json)",
    )
    parser.add_argument("--section-id", default=None, help="Section id when dump has multiple blackboards")
    parser.add_argument("--similarity", type=float, default=_DEFAULT_SIM, help="Jaccard threshold (default: 0.85)")
    parser.add_argument("--max-items", type=int, default=_DEFAULT_MAX_ITEMS, help="Injected top-N for cost (default: 8)")
    parser.add_argument("--near-dup-threshold", type=float, default=0.70, help="Verdict: near_dup rate above this")
    parser.add_argument(
        "--non-finding-threshold",
        type=float,
        default=0.10,
        help="Verdict: non-finding share below this",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Optional path to write JSON report",
    )
    args = parser.parse_args(argv)

    path = Path(args.dump)
    if not path.is_file():
        print(f"Dump not found: {path}", file=sys.stderr)
        return 1

    data = _load_dump(path)
    section_id = _resolve_section_id(data, args.section_id)
    report = audit_dump(
        data,
        section_id=section_id,
        similarity=args.similarity,
        max_items=args.max_items,
        near_dup_threshold=args.near_dup_threshold,
        non_finding_threshold=args.non_finding_threshold,
    )
    report["dump_path"] = str(path)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        _print_human(report)
        if args.out:
            print(f"\nwrote: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
