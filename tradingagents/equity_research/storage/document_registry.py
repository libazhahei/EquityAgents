"""Document registry CRUD."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime
from typing import Any

from tradingagents.equity_research.storage.db import DocumentRegistryRow, get_session


def _fingerprint(ticker: str, source_type: str, title: str, published_date: str | None) -> str:
    raw = f"{ticker}|{source_type}|{title}|{published_date or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()


class DocumentRegistry:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def register(
        self,
        ticker: str,
        source_type: str,
        title: str = "",
        source_url: str = "",
        published_date: str | None = None,
        fiscal_period: str | None = None,
        access_path: str | None = None,
        file_hash: str | None = None,
    ) -> dict[str, Any]:
        fp = _fingerprint(ticker, source_type, title, published_date)
        session = get_session(self.config)
        try:
            existing = session.query(DocumentRegistryRow).filter_by(doc_fingerprint=fp).first()
            if existing:
                return self._row_to_dict(existing)
            doc_id = str(uuid.uuid4())
            pub = None
            if published_date:
                try:
                    pub = date.fromisoformat(published_date[:10])
                except ValueError:
                    pub = None
            row = DocumentRegistryRow(
                doc_id=doc_id,
                ticker=ticker.upper(),
                source_type=source_type,
                title=title,
                published_date=pub,
                fiscal_period=fiscal_period,
                source_url=source_url,
                access_path=access_path,
                file_hash=file_hash,
                doc_fingerprint=fp,
            )
            session.add(row)
            session.commit()
            return self._row_to_dict(row)
        finally:
            session.close()

    def get_by_id(self, doc_id: str) -> dict[str, Any] | None:
        session = get_session(self.config)
        try:
            row = session.query(DocumentRegistryRow).filter_by(doc_id=doc_id).first()
            return self._row_to_dict(row) if row else None
        finally:
            session.close()

    def list_by_ticker(self, ticker: str) -> list[dict[str, Any]]:
        session = get_session(self.config)
        try:
            rows = session.query(DocumentRegistryRow).filter_by(ticker=ticker.upper()).all()
            return [self._row_to_dict(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def _row_to_dict(row: DocumentRegistryRow) -> dict[str, Any]:
        return {
            "doc_id": row.doc_id,
            "ticker": row.ticker,
            "source_type": row.source_type,
            "title": row.title,
            "published_date": row.published_date.isoformat() if row.published_date else None,
            "fiscal_period": row.fiscal_period,
            "source_url": row.source_url,
            "retrieved_at": row.retrieved_at.isoformat() if row.retrieved_at else None,
            "file_hash": row.file_hash,
            "access_path": row.access_path,
            "doc_fingerprint": row.doc_fingerprint,
            "processing_status": row.processing_status,
            "reliability_score": float(getattr(row, "reliability_score", 0.5) or 0.5),
            "citation_count": int(getattr(row, "citation_count", 0) or 0),
            "last_used_at": (
                row.last_used_at.isoformat() if getattr(row, "last_used_at", None) else None
            ),
        }

    def update_reliability(
        self,
        doc_id: str,
        delta: float,
        reason: str = "",
    ) -> dict[str, Any] | None:
        session = get_session(self.config)
        try:
            row = session.query(DocumentRegistryRow).filter_by(doc_id=doc_id).first()
            if not row:
                return None
            current = float(getattr(row, "reliability_score", 0.5) or 0.5)
            row.reliability_score = max(0.0, min(1.0, current + delta))
            row.citation_count = int(getattr(row, "citation_count", 0) or 0) + (1 if delta > 0 else 0)
            row.last_used_at = datetime.utcnow()
            session.commit()
            return self._row_to_dict(row)
        finally:
            session.close()
