"""Structured fact store."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.storage.db import StructuredFactRow, get_session


class FactStore:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def insert(
        self,
        ticker: str,
        metric_name: str,
        metric_value: float | None = None,
        metric_value_text: str | None = None,
        *,
        unit: str = "",
        fiscal_period: str = "",
        segment: str = "",
        source_doc_id: str = "",
        extraction_confidence: float = 0.8,
    ) -> dict[str, Any]:
        fact_id = str(uuid.uuid4())
        session = get_session(self.config)
        try:
            row = StructuredFactRow(
                fact_id=fact_id,
                ticker=ticker.upper(),
                metric_name=metric_name,
                metric_value=metric_value,
                metric_value_text=metric_value_text,
                unit=unit,
                fiscal_period=fiscal_period,
                segment=segment,
                source_doc_id=source_doc_id,
                extraction_confidence=extraction_confidence,
            )
            session.add(row)
            session.commit()
            return self._row_to_dict(row)
        finally:
            session.close()

    def get_latest(
        self,
        ticker: str,
        metric_name: str,
        fiscal_period: str | None = None,
    ) -> dict[str, Any] | None:
        session = get_session(self.config)
        try:
            q = session.query(StructuredFactRow).filter_by(
                ticker=ticker.upper(),
                metric_name=metric_name,
            )
            if fiscal_period:
                q = q.filter_by(fiscal_period=fiscal_period)
            row = q.order_by(StructuredFactRow.data_version.desc()).first()
            return self._row_to_dict(row) if row else None
        finally:
            session.close()

    def list_by_ticker(self, ticker: str) -> list[dict[str, Any]]:
        session = get_session(self.config)
        try:
            rows = session.query(StructuredFactRow).filter_by(ticker=ticker.upper()).all()
            return [self._row_to_dict(r) for r in rows]
        finally:
            session.close()

    @staticmethod
    def _row_to_dict(row: StructuredFactRow) -> dict[str, Any]:
        return {
            "fact_id": row.fact_id,
            "ticker": row.ticker,
            "metric_name": row.metric_name,
            "metric_value": row.metric_value,
            "metric_value_text": row.metric_value_text,
            "unit": row.unit,
            "fiscal_period": row.fiscal_period,
            "segment": row.segment,
            "source_doc_id": row.source_doc_id,
            "extraction_confidence": row.extraction_confidence,
            "data_version": row.data_version,
        }
