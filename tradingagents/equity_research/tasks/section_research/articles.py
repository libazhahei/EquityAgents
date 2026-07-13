"""Per-question article files and reference merging for section research."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tradingagents.equity_research.tools.findings_cache_tools import (
    articles_dir,
    resolve_section_artifact_dir,
)

_REF_TOKEN_RE = re.compile(r"\[(\d+)\]")


def _safe_qid(qid: str) -> str:
    return re.sub(r"[^\w.\-]+", "_", str(qid or "q").strip()) or "q"


def article_paths(artifact_dir: Path, qid: str) -> tuple[Path, Path]:
    safe = _safe_qid(qid)
    return artifact_dir / f"article_{safe}.md", artifact_dir / f"refs_{safe}.json"


def _citation_url(cit: Any) -> str:
    if isinstance(cit, dict):
        return str(cit.get("url") or cit.get("traceable_ref") or cit.get("link") or "").strip()
    return str(getattr(cit, "url", "") or "").strip()


def _citation_title(cit: Any) -> str:
    if isinstance(cit, dict):
        return str(cit.get("title") or cit.get("source") or cit.get("source_type") or "").strip()
    return str(getattr(cit, "title", "") or getattr(cit, "source", "") or "").strip()


def _fact_line(fact: Any, ref_map: dict[str, dict[str, str]]) -> str:
    if not isinstance(fact, dict):
        text = str(fact)
        return f"- {text}" if text else ""
    parts: list[str] = []
    for key in ("metric", "value", "unit", "period", "quote", "text", "claim", "snippet"):
        val = fact.get(key)
        if val not in (None, ""):
            parts.append(f"{key}={val}" if key != "quote" and key != "text" else str(val))
    url = str(fact.get("url") or fact.get("source_url") or "").strip()
    if not url and isinstance(fact.get("citation"), dict):
        url = _citation_url(fact["citation"])
    ref = ""
    if url:
        n = _ensure_ref(ref_map, url, title=str(fact.get("source") or fact.get("source_type") or ""))
        ref = f" [{n}]"
    body = "; ".join(parts) if parts else json.dumps(fact, default=str, ensure_ascii=False)[:300]
    return f"- {body}{ref}"


def _ensure_ref(ref_map: dict[str, dict[str, str]], url: str, *, title: str = "") -> str:
    for num, meta in ref_map.items():
        if meta.get("url") == url:
            return num
    num = str(len(ref_map) + 1)
    ref_map[num] = {"url": url, "title": title}
    return num


def _analysis_with_refs(
    draft: str,
    citations: list[Any],
    ref_map: dict[str, dict[str, str]],
) -> str:
    text = (draft or "").strip()
    # Strip bare URLs that already appear in citations; replace with [n] if missing.
    for cit in citations:
        url = _citation_url(cit)
        if not url:
            continue
        n = _ensure_ref(ref_map, url, title=_citation_title(cit))
        if url in text and f"[{n}]" not in text:
            text = text.replace(url, f"[{n}]")
    for cit in citations:
        url = _citation_url(cit)
        if url:
            _ensure_ref(ref_map, url, title=_citation_title(cit))
    return text


def render_answer_card_article(card: Any, *, question_text: str = "") -> tuple[str, dict[str, dict[str, str]]]:
    """Build markdown + local refs map from an AnswerCard-like object/dict."""
    if hasattr(card, "model_dump"):
        data = card.model_dump()
    elif isinstance(card, dict):
        data = card
    else:
        data = {}

    qid = str(data.get("question_id") or "")
    question = question_text or str(data.get("question") or qid)
    short_answer = str(data.get("short_answer") or "").strip()
    draft = str(data.get("draft_paragraph") or "").strip()
    facts = list(data.get("verified_facts") or [])
    gaps = list(data.get("open_gaps") or [])
    citations = list(data.get("citations") or [])
    # Also fold source_attributions urls
    for sa in data.get("source_attributions") or []:
        if isinstance(sa, dict) and sa.get("url"):
            citations.append(sa)
        elif hasattr(sa, "url") and getattr(sa, "url", None):
            citations.append({"url": sa.url, "title": getattr(sa, "title", "")})

    ref_map: dict[str, dict[str, str]] = {}
    fact_lines = [_fact_line(f, ref_map) for f in facts]
    fact_lines = [ln for ln in fact_lines if ln]
    analysis = _analysis_with_refs(draft or short_answer, citations, ref_map)
    gap_lines = [f"- {g}" for g in gaps if str(g).strip()]

    md = "\n".join([
        f"# Q: {question}",
        "",
        "## Short Answer",
        short_answer or "(pending)",
        "",
        "## Key Facts",
        "\n".join(fact_lines) if fact_lines else "- (none yet)",
        "",
        "## Analysis",
        analysis or "(pending)",
        "",
        "## Open Gaps",
        "\n".join(gap_lines) if gap_lines else "- (none)",
        "",
    ])
    return md, ref_map


def write_question_article(
    state: dict[str, Any],
    qid: str,
    card: Any,
    *,
    question_text: str = "",
) -> dict[str, str]:
    """Overwrite article_<qid>.md and refs_<qid>.json for the active question."""
    artifact_dir = resolve_section_artifact_dir(state)
    md_path, refs_path = article_paths(artifact_dir, qid)
    md, ref_map = render_answer_card_article(card, question_text=question_text)
    md_path.write_text(md, encoding="utf-8")
    refs_path.write_text(json.dumps(ref_map, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "section_artifact_dir": str(artifact_dir),
        "article_path": str(md_path),
        "refs_path": str(refs_path),
    }


def list_question_articles(artifact_dir: Path | str) -> list[tuple[str, Path, Path]]:
    """Return (qid, article_path, refs_path) sorted by filename."""
    root = Path(artifact_dir)
    if not root.exists():
        return []
    articles = sorted(root.glob("article_*.md"))
    out: list[tuple[str, Path, Path]] = []
    for art in articles:
        stem = art.stem  # article_<qid>
        qid = stem[len("article_"):] if stem.startswith("article_") else stem
        refs = root / f"refs_{qid}.json"
        out.append((qid, art, refs))
    return out


def _load_refs(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(k): {
            "url": str((v or {}).get("url") or ""),
            "title": str((v or {}).get("title") or ""),
        }
        for k, v in data.items()
        if isinstance(v, dict)
    }


def merge_articles_and_refs(
    artifact_dir: Path | str,
    *,
    executive_summary: str = "",
    include_article_chapters: bool = True,
) -> tuple[str, dict[str, dict[str, str]]]:
    """Merge per-question articles with URL-deduped global reference renumbering."""
    entries = list_question_articles(artifact_dir)
    global_refs: dict[str, dict[str, str]] = {}
    url_to_num: dict[str, str] = {}
    chapters: list[str] = []

    for _qid, art_path, refs_path in entries:
        local_refs = _load_refs(refs_path)
        local_to_global: dict[str, str] = {}
        for local_n, meta in local_refs.items():
            url = (meta.get("url") or "").strip()
            if not url:
                continue
            if url not in url_to_num:
                num = str(len(url_to_num) + 1)
                url_to_num[url] = num
                global_refs[num] = {"url": url, "title": meta.get("title") or ""}
            else:
                num = url_to_num[url]
                if meta.get("title") and not global_refs[num].get("title"):
                    global_refs[num]["title"] = meta["title"]
            local_to_global[local_n] = url_to_num[url]

        body = art_path.read_text(encoding="utf-8")

        def _rewrite(match: re.Match[str]) -> str:
            local_n = match.group(1)
            if local_n in local_to_global:
                return f"[{local_to_global[local_n]}]"
            return match.group(0)

        chapters.append(_REF_TOKEN_RE.sub(_rewrite, body).rstrip())

    parts: list[str] = []
    if executive_summary.strip():
        # If the LLM already produced a full report, keep it as the main body.
        body = executive_summary.strip()
        if body.lstrip().startswith("#"):
            parts.append(body)
        else:
            parts.append("# Executive Summary\n\n" + body)
    if include_article_chapters and chapters:
        parts.append("# Appendix: Per-Question Detail\n\n" + "\n\n---\n\n".join(chapters))
    if global_refs:
        parts.append("# References\n\n" + format_references_markdown(global_refs))
    report = "\n\n".join(parts).strip() + "\n"
    return report, global_refs


def format_references_markdown(global_refs: dict[str, dict[str, str]]) -> str:
    ref_lines = []
    for n in sorted(global_refs.keys(), key=lambda x: int(x) if x.isdigit() else x):
        meta = global_refs[n]
        title = meta.get("title") or ""
        url = meta.get("url") or ""
        label = f"{title} — {url}" if title else url
        ref_lines.append(f"[{n}] {label}")
    return "\n".join(ref_lines)


def build_global_refs_and_articles_for_prompt(
    artifact_dir: Path | str,
) -> tuple[str, dict[str, dict[str, str]]]:
    """Renumber local article refs to a global map for the finalizer prompt."""
    entries = list_question_articles(artifact_dir)
    global_refs: dict[str, dict[str, str]] = {}
    url_to_num: dict[str, str] = {}
    chunks: list[str] = []

    for qid, art_path, refs_path in entries:
        local_refs = _load_refs(refs_path)
        local_to_global: dict[str, str] = {}
        for local_n, meta in local_refs.items():
            url = (meta.get("url") or "").strip()
            if not url:
                continue
            if url not in url_to_num:
                num = str(len(url_to_num) + 1)
                url_to_num[url] = num
                global_refs[num] = {"url": url, "title": meta.get("title") or ""}
            else:
                num = url_to_num[url]
                if meta.get("title") and not global_refs[num].get("title"):
                    global_refs[num]["title"] = meta["title"]
            local_to_global[str(local_n)] = url_to_num[url]

        body = art_path.read_text(encoding="utf-8")

        def _rewrite(match: re.Match[str], mapping: dict[str, str] = local_to_global) -> str:
            local_n = match.group(1)
            if local_n in mapping:
                return f"[{mapping[local_n]}]"
            return match.group(0)

        rewritten = _REF_TOKEN_RE.sub(_rewrite, body)
        chunks.append(f"<!-- question_id={qid} -->\n{rewritten}")

    articles_text = "\n\n---\n\n".join(chunks)
    if global_refs:
        articles_text += (
            "\n\n### Global reference list (use these [n] markers in the report)\n"
            + format_references_markdown(global_refs)
        )
    return articles_text, global_refs


def concat_articles_for_prompt(artifact_dir: Path | str) -> str:
    """Concatenate article markdown for finalizer LLM input with global [n] refs."""
    text, _refs = build_global_refs_and_articles_for_prompt(artifact_dir)
    return text


def assemble_final_report(
    *,
    llm_report: str,
    artifact_dir: Path | str,
    include_article_appendix: bool = True,
) -> tuple[str, dict[str, dict[str, str]]]:
    """Assemble complete final report: LLM narrative + optional appendix + merged refs."""
    return merge_articles_and_refs(
        artifact_dir,
        executive_summary=llm_report,
        include_article_chapters=include_article_appendix,
    )
