"""RAG-backed filings search."""

from __future__ import annotations

from datetime import date, datetime
import re
from typing import Any

from tradingagents.rag.types import CorpusScope, Document, SearchQuery

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "to", "with",
}
_RECENT_QUERY_RE = re.compile(r"\b(recent|latest|quarter|quarters|qoq|trend|last few)\b", re.I)
_LOW_INFO_RE = re.compile(r"\b(?:refer\s+to|discussion\s+below|see\s+below)\b", re.I)
_NUMERIC_RE = re.compile(r"(?:\b\d+(?:\.\d+)?%|\$\s?\d[\d,]*(?:\.\d+)?)")
_CAUSAL_RE = re.compile(r"\b(?:primarily|driven by|due to|because|as a result|offset by|impact)\b", re.I)


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


def _query_terms(query: str) -> set[str]:
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    return {t for t in terms if len(t) > 2 and t not in _STOPWORDS}


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _is_low_information(text: str) -> bool:
    normalized = _normalize_text(text)
    words = normalized.split()
    if len(words) < 10 and not _NUMERIC_RE.search(text):
        return True
    if _LOW_INFO_RE.search(text):
        return True
    return False


def _stage2_score(
    *,
    rrf_score: float,
    text: str,
    query_term_set: set[str],
    info_score_seed: float,
    form: str | None,
    prefer_recent: bool,
) -> float:
    normalized = _normalize_text(text)
    score = float(rrf_score)
    if query_term_set:
        overlap = sum(1 for t in query_term_set if t in normalized)
        score += 0.002 * overlap
    score += min(max(info_score_seed, 0.0), 1.0) * 0.004
    if _NUMERIC_RE.search(text):
        score += 0.003
    if _CAUSAL_RE.search(text):
        score += 0.004
    if _is_low_information(text):
        score -= 0.01
    if prefer_recent and form == "10-Q":
        score += 0.008
    elif prefer_recent and form == "10-K":
        score -= 0.002
    return score


def _apply_post_processing(
    hits: list[dict[str, Any]],
    *,
    keywords: str,
    top_k: int,
    max_chars: int,
    dedupe: bool,
    rerank: bool,
    prefer_recent: bool,
    max_per_group: int,
) -> list[dict[str, Any]]:
    if not hits:
        return []

    query_term_set = _query_terms(keywords)
    transformed: list[dict[str, Any]] = []
    for h in hits:
        text = h.get("chunk_text", "")
        group = "|".join(
            [
                str(h.get("accession_number") or ""),
                str(h.get("section") or ""),
                str(h.get("subsection_key") or ""),
            ]
        )
        base_score = float(h.get("rrf_score", 0.0))
        info_seed = float(h.get("info_score_seed") or 0.0)
        final_score = (
            _stage2_score(
                rrf_score=base_score,
                text=text,
                query_term_set=query_term_set,
                info_score_seed=info_seed,
                form=h.get("form"),
                prefer_recent=prefer_recent,
            )
            if rerank
            else base_score
        )
        h["final_score"] = final_score
        h["dedupe_group"] = group
        h["_date_obj"] = _parse_date(h.get("filing_date"))
        transformed.append(h)

    transformed.sort(
        key=lambda x: (
            float(x.get("final_score", 0.0)),
            x["_date_obj"] or date.min,
            -int(x.get("chunk_index") or 0),
        ),
        reverse=True,
    )

    selected: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    group_counts: dict[str, int] = {}

    for hit in transformed:
        if len(selected) >= top_k:
            break

        if dedupe:
            signature = str(hit.get("content_hash") or "") or _normalize_text(hit.get("chunk_text", ""))[:500]
            if signature in seen_signatures:
                continue

        group = str(hit.get("dedupe_group") or "")
        if max_per_group > 0 and group and group_counts.get(group, 0) >= max_per_group:
            continue

        selected.append(hit)
        group_counts[group] = group_counts.get(group, 0) + 1
        if dedupe:
            seen_signatures.add(signature)

    if len(selected) < top_k:
        for hit in transformed:
            if len(selected) >= top_k:
                break
            if hit in selected:
                continue
            selected.append(hit)

    total = 0
    trimmed: list[dict[str, Any]] = []
    for hit in selected:
        text = hit.get("chunk_text", "")
        if total + len(text) > max_chars and trimmed:
            break
        trimmed.append(hit)
        total += len(text)

    for hit in trimmed:
        hit.pop("_date_obj", None)
    return trimmed


def filings_search_rag(
    deps: Any,
    ticker: str,
    keywords: str,
    *,
    form_type: str | None = None,
    section: str | None = None,
    top_k: int = 8,
    max_chars: int = 8000,
    dedupe: bool = True,
    rerank: bool = True,
    prefer_recent: bool | None = None,
    max_per_group: int = 2,
) -> dict[str, Any]:
    if not keywords or not keywords.strip():
        return {
            "error": "keywords required — provide search terms relevant to your research question",
            "ticker": ticker.upper(),
            "hits": [],
        }
    if deps.rag is None:
        return {"error": "RAG service unavailable", "ticker": ticker.upper(), "hits": []}

    should_prefer_recent = (
        bool(prefer_recent)
        if prefer_recent is not None
        else (form_type is None and bool(_RECENT_QUERY_RE.search(keywords)))
    )
    pool_top_k = min(max(top_k * 4, top_k), 64) if (dedupe or rerank) else top_k
    pool_max_chars = max_chars * 3 if (dedupe or rerank) else max_chars

    result = deps.rag.search(
        "sec_filings",
        SearchQuery(
            keywords=keywords.strip(),
            filters={
                "ticker": ticker.upper(),
                "form": form_type,
                "section": section,
            },
            top_k=pool_top_k,
            max_chars=pool_max_chars,
        ),
    )
    raw_hits = [
        {
            "chunk_text": h.text,
            "rrf_score": h.score,
            "form": h.metadata.get("form"),
            "filing_date": h.metadata.get("filing_date"),
            "section": h.metadata.get("section"),
            "accession_number": h.metadata.get("accession_number"),
            "url": h.metadata.get("source_url"),
            "chunk_index": h.metadata.get("chunk_index"),
            "chunk_type": h.metadata.get("chunk_type"),
            "subsection_title": h.metadata.get("subsection_title"),
            "subsection_key": h.metadata.get("subsection_key"),
            "content_hash": h.metadata.get("content_hash"),
            "info_score_seed": h.metadata.get("info_score_seed"),
        }
        for h in result.hits
    ]
    hits = _apply_post_processing(
        raw_hits,
        keywords=keywords.strip(),
        top_k=top_k,
        max_chars=max_chars,
        dedupe=dedupe,
        rerank=rerank,
        prefer_recent=should_prefer_recent,
        max_per_group=max_per_group,
    )
    total_chars = sum(len(h.get("chunk_text", "")) for h in hits)
    return {
        "ticker": ticker.upper(),
        "keywords": result.keywords,
        "hits": hits,
        "total_chars": total_chars,
        "indexed": result.indexed,
        "prefer_recent": should_prefer_recent,
        **result.extra,
    }


def ingest_evidence_document(
    deps: Any,
    *,
    ticker: str,
    fragment_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Index a single evidence excerpt via the RAG evidence corpus."""
    if deps.rag is None or not text.strip():
        return
    meta = dict(metadata or {})
    meta.setdefault("fragment_id", fragment_id)
    meta.setdefault("ticker", ticker.upper())
    deps.rag.ingest(
        "evidence",
        CorpusScope(
            ticker=ticker.upper(),
            documents=[
                Document(doc_key=fragment_id, text=text, metadata=meta),
            ],
        ),
    )
