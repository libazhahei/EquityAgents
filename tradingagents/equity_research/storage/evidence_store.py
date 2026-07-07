"""Evidence fragment storage with optional pgvector search."""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from tradingagents.equity_research.storage.db import EvidenceFragmentRow, get_engine, get_session


class EvidenceStore:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def insert(
        self,
        ticker: str,
        doc_id: str,
        excerpt_text: str,
        *,
        fragment_type: str = "general",
        source_reliability: str = "medium",
        hypothesis_id: str | None = None,
        extraction_confidence: float = 0.5,
        embedding: list[float] | None = None,
        excerpt_context: str = "",
        fragment_id: str | None = None,
    ) -> dict[str, Any]:
        fragment_id = fragment_id or str(uuid.uuid4())
        session = get_session(self.config)
        try:
            row = EvidenceFragmentRow(
                fragment_id=fragment_id,
                doc_id=doc_id,
                ticker=ticker.upper(),
                excerpt_text=excerpt_text,
                excerpt_context=excerpt_context,
                fragment_type=fragment_type,
                source_reliability=source_reliability,
                hypothesis_id=hypothesis_id,
                extraction_confidence=extraction_confidence,
                embedding=json.dumps(embedding) if embedding else None,
            )
            session.add(row)
            session.commit()
            if embedding:
                self._upsert_vector(fragment_id, embedding)
            return self._row_to_dict(row, embedding)
        finally:
            session.close()

    def _upsert_vector(self, fragment_id: str, embedding: list[float]) -> None:
        engine = get_engine(self.config)
        vec_literal = "[" + ",".join(str(x) for x in embedding) + "]"
        with engine.connect() as conn:
            try:
                conn.execute(
                    text(
                        "UPDATE evidence_fragment SET embedding_vec = CAST(:vec AS vector) "
                        "WHERE fragment_id = :fid"
                    ),
                    {"vec": vec_literal, "fid": fragment_id},
                )
                conn.commit()
            except Exception:
                conn.rollback()

    def search_similar(
        self,
        ticker: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        engine = get_engine(self.config)
        vec_literal = "[" + ",".join(str(x) for x in query_embedding) + "]"
        with engine.connect() as conn:
            try:
                result = conn.execute(
                    text(
                        """
                        SELECT fragment_id, doc_id, excerpt_text, fragment_type,
                               source_reliability, hypothesis_id,
                               1 - (embedding_vec <=> CAST(:vec AS vector)) AS score
                        FROM evidence_fragment
                        WHERE ticker = :ticker AND embedding_vec IS NOT NULL
                        ORDER BY embedding_vec <=> CAST(:vec AS vector)
                        LIMIT :k
                        """
                    ),
                    {"vec": vec_literal, "ticker": ticker.upper(), "k": top_k},
                )
                return [dict(row._mapping) for row in result]
            except Exception:
                return self._fallback_text_search(ticker, top_k)

    def _fallback_text_search(self, ticker: str, top_k: int) -> list[dict[str, Any]]:
        session = get_session(self.config)
        try:
            rows = (
                session.query(EvidenceFragmentRow)
                .filter_by(ticker=ticker.upper())
                .limit(top_k)
                .all()
            )
            return [self._row_to_dict(r) for r in rows]
        finally:
            session.close()

    def list_by_ticker(self, ticker: str) -> list[dict[str, Any]]:
        session = get_session(self.config)
        try:
            rows = session.query(EvidenceFragmentRow).filter_by(ticker=ticker.upper()).all()
            return [self._row_to_dict(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def _row_to_dict(row: EvidenceFragmentRow, embedding: list[float] | None = None) -> dict[str, Any]:
        return {
            "fragment_id": row.fragment_id,
            "doc_id": row.doc_id,
            "ticker": row.ticker,
            "excerpt_text": row.excerpt_text,
            "excerpt_context": row.excerpt_context,
            "fragment_type": row.fragment_type,
            "source_reliability": row.source_reliability,
            "hypothesis_id": row.hypothesis_id,
            "extraction_confidence": row.extraction_confidence,
            "embedding": embedding,
        }
