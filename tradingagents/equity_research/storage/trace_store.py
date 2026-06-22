"""Research trace audit log."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.storage.db import ResearchTraceRow, get_session


class TraceStore:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def append(
        self,
        report_id: str,
        ticker: str,
        node_name: str,
        payload: dict[str, Any],
        *,
        hypothesis_id: str | None = None,
        section_id: str | None = None,
    ) -> dict[str, Any]:
        trace_id = str(uuid.uuid4())
        session = get_session(self.config)
        try:
            row = ResearchTraceRow(
                trace_id=trace_id,
                report_id=report_id,
                ticker=ticker.upper(),
                node_name=node_name,
                hypothesis_id=hypothesis_id,
                section_id=section_id,
                payload=payload,
            )
            session.add(row)
            session.commit()
            return {
                "trace_id": trace_id,
                "report_id": report_id,
                "ticker": ticker.upper(),
                "node_name": node_name,
                "hypothesis_id": hypothesis_id,
                "section_id": section_id,
                "payload": payload,
            }
        finally:
            session.close()
