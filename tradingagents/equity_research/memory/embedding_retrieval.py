"""Embedding-based semantic similarity for memory retrieval."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.memory.similarity import cosine_similarity, _text_similarity


def _use_embedding(deps: Any | None) -> bool:
    if deps is None:
        return False
    er = getattr(deps, "config", {}).get("equity_research", {})
    if not er.get("memory_use_embedding", True):
        return False
    return hasattr(deps, "embeddings") and (hasattr(deps, "evidence") or hasattr(deps, "rag"))


def _rag_evidence_scores(deps: Any, ticker: str, query: str, top_k: int) -> dict[str, float]:
    if not hasattr(deps, "rag") or deps.rag is None or not query:
        return {}
    from tradingagents.rag.types import SearchQuery

    try:
        result = deps.rag.search(
            "evidence",
            SearchQuery(keywords=query, filters={"ticker": ticker}, top_k=top_k, max_chars=1_000_000),
        )
    except Exception:
        return {}
    scores: dict[str, float] = {}
    for hit in result.hits:
        fid = hit.metadata.get("fragment_id", hit.chunk_id)
        scores[str(fid)] = max(scores.get(str(fid), 0.0), float(hit.score))
        eid = hit.metadata.get("evidence_id")
        if eid:
            scores[str(eid)] = max(scores.get(str(eid), 0.0), float(hit.score))
    return scores


def semantic_similarity(
    deps: Any | None,
    query: str,
    text: str,
    *,
    ticker: str,
    fragment_id: str = "",
) -> float:
    """Score query→text relevance using embeddings when deps are available."""
    if not query or not text:
        return 0.0
    if not _use_embedding(deps):
        return _text_similarity(query, text)

    query_emb = deps.embeddings.embed(query)
    if fragment_id and hasattr(deps, "evidence"):
        for frag in deps.evidence.list_by_ticker(ticker):
            if frag.get("fragment_id") == fragment_id:
                stored = frag.get("embedding")
                if stored:
                    return cosine_similarity(query_emb, stored)
                break

    text_emb = deps.embeddings.embed(text)
    emb_score = cosine_similarity(query_emb, text_emb)
    if emb_score > 0:
        return emb_score

    if hasattr(deps, "rag") and deps.rag is not None and fragment_id:
        rag_scores = _rag_evidence_scores(deps, ticker, query, top_k=30)
        if fragment_id in rag_scores:
            return rag_scores[fragment_id]

    if hasattr(deps, "evidence"):
        er = deps.config.get("equity_research", {})
        top_k = int(er.get("memory_semantic_top_k", 30))
        hits = deps.evidence.search_similar(ticker, query_emb, top_k=top_k)
        if fragment_id:
            for hit in hits:
                if hit.get("fragment_id") == fragment_id:
                    return float(hit.get("score", 0.0))
        for hit in hits:
            if hit.get("excerpt_text", "")[:120] == text[:120]:
                return float(hit.get("score", 0.0))
    return max(emb_score, _text_similarity(query, text) * 0.5)


def hybrid_evidence_candidates(
    deps: Any | None,
    state: dict[str, Any],
    query: str,
    *,
    top_k: int = 30,
) -> dict[str, float]:
    """Return evidence_id → semantic score from RAG search merged with ledger ids."""
    scores: dict[str, float] = {}
    ticker = state.get("ticker", "")
    ledger = state.get("evidence_ledger", [])

    if _use_embedding(deps) and ticker and query:
        rag_scores = _rag_evidence_scores(deps, ticker, query, top_k=top_k)
        scores.update(rag_scores)
        if not rag_scores and hasattr(deps, "evidence"):
            query_emb = deps.embeddings.embed(query)
            for hit in deps.evidence.search_similar(ticker, query_emb, top_k=top_k):
                fid = hit.get("fragment_id", "")
                if fid:
                    scores[fid] = max(scores.get(fid, 0.0), float(hit.get("score", 0.0)))

    for entry in ledger:
        eid = entry.get("evidence_id", "")
        if not eid:
            continue
        quote = entry.get("quote", "")
        score = semantic_similarity(
            deps, query, quote, ticker=ticker, fragment_id=entry.get("fragment_id", eid)
        )
        scores[eid] = max(scores.get(eid, 0.0), score)
    return scores
