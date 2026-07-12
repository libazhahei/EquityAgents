"""Blackboard session storage — persists full blackboard content and summaries.

Full session blackboard entries are stored to database (or in-memory fallback).
After session ends, an LLM-generated summary is saved for later sessions to reference.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class BlackboardStore:
    """Database-backed blackboard session storage (PostgreSQL)."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}
        self._engine = None
        try:
            from tradingagents.equity_research.storage.db import get_engine
            self._engine = get_engine(self._config)
            # Test connection
            with self._engine.connect() as conn:
                conn.execute(__import__("sqlalchemy").text("SELECT 1"))
            self._ensure_table()
        except Exception as exc:
            logger.warning("BlackboardStore: PostgreSQL unavailable (%s), using in-memory", exc)
            self._engine = None

    def _ensure_table(self) -> None:
        if self._engine is None:
            return
        try:
            from sqlalchemy import text
            with self._engine.begin() as conn:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS blackboard_sessions (
                        id SERIAL PRIMARY KEY,
                        report_id VARCHAR(255) NOT NULL,
                        section_id VARCHAR(255) NOT NULL,
                        ticker VARCHAR(50) NOT NULL DEFAULT '',
                        entries JSONB NOT NULL DEFAULT '[]'::jsonb,
                        summary TEXT NOT NULL DEFAULT '',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        UNIQUE(report_id, section_id)
                    )
                """))
        except Exception as exc:
            logger.warning("BlackboardStore: failed to create table: %s", exc)

    def save_session_blackboard(
        self,
        report_id: str,
        section_id: str,
        entries: list[dict[str, Any]],
        *,
        ticker: str = "",
    ) -> None:
        """Save full blackboard entries for a session."""
        if self._engine is None:
            return
        try:
            from sqlalchemy import text
            with self._engine.begin() as conn:
                # Upsert
                conn.execute(text("""
                    INSERT INTO blackboard_sessions (report_id, section_id, ticker, entries, updated_at)
                    VALUES (:report_id, :section_id, :ticker, CAST(:entries AS jsonb), NOW())
                    ON CONFLICT (report_id, section_id)
                    DO UPDATE SET entries = CAST(:entries AS jsonb), ticker = :ticker, updated_at = NOW()
                """), {
                    "report_id": report_id,
                    "section_id": section_id,
                    "ticker": ticker,
                    "entries": __import__("json").dumps(entries),
                })
        except Exception as exc:
            logger.warning("BlackboardStore: save failed: %s", exc)

    def save_session_summary(
        self,
        report_id: str,
        section_id: str,
        summary: str,
    ) -> None:
        """Save LLM-generated summary for a session."""
        if self._engine is None:
            return
        try:
            from sqlalchemy import text
            with self._engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO blackboard_sessions (report_id, section_id, summary, updated_at)
                    VALUES (:report_id, :section_id, :summary, NOW())
                    ON CONFLICT (report_id, section_id)
                    DO UPDATE SET summary = :summary, updated_at = NOW()
                """), {
                    "report_id": report_id,
                    "section_id": section_id,
                    "summary": summary,
                })
        except Exception as exc:
            logger.warning("BlackboardStore: save summary failed: %s", exc)

    def load_session_summary(self, report_id: str, section_id: str) -> str:
        """Load the summary for a specific session."""
        if self._engine is None:
            return ""
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT summary FROM blackboard_sessions
                    WHERE report_id = :report_id AND section_id = :section_id
                """), {"report_id": report_id, "section_id": section_id})
                row = result.fetchone()
                return row[0] if row else ""
        except Exception as exc:
            logger.warning("BlackboardStore: load summary failed: %s", exc)
            return ""

    def get_prior_sessions_summaries(
        self,
        report_id: str,
        exclude_section_id: str | None = None,
    ) -> list[dict[str, str]]:
        """Get summaries of all prior sessions for a report.

        Returns list of {"section_id": "...", "summary": "..."} dicts.
        """
        if self._engine is None:
            return []
        try:
            from sqlalchemy import text
            with self._engine.connect() as conn:
                if exclude_section_id:
                    result = conn.execute(text("""
                        SELECT section_id, summary FROM blackboard_sessions
                        WHERE report_id = :report_id
                          AND section_id != :exclude_section_id
                          AND summary != ''
                        ORDER BY created_at ASC
                    """), {"report_id": report_id, "exclude_section_id": exclude_section_id})
                else:
                    result = conn.execute(text("""
                        SELECT section_id, summary FROM blackboard_sessions
                        WHERE report_id = :report_id
                          AND summary != ''
                        ORDER BY created_at ASC
                    """), {"report_id": report_id})
                return [
                    {"section_id": row[0], "summary": row[1]}
                    for row in result.fetchall()
                ]
        except Exception as exc:
            logger.warning("BlackboardStore: get prior summaries failed: %s", exc)
            return []


class InMemoryBlackboardStore:
    """In-memory fallback for blackboard storage (no database required)."""

    _sessions: dict[str, dict[str, Any]] = {}  # key: "report_id:section_id"

    @classmethod
    def reset(cls) -> None:
        cls._sessions.clear()

    @classmethod
    def _key(cls, report_id: str, section_id: str) -> str:
        return f"{report_id}:{section_id}"

    def save_session_blackboard(
        self,
        report_id: str,
        section_id: str,
        entries: list[dict[str, Any]],
        *,
        ticker: str = "",
    ) -> None:
        key = self._key(report_id, section_id)
        if key not in self._sessions:
            self._sessions[key] = {
                "report_id": report_id,
                "section_id": section_id,
                "ticker": ticker,
                "entries": [],
                "summary": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        self._sessions[key]["entries"] = entries
        if ticker:
            self._sessions[key]["ticker"] = ticker

    def save_session_summary(
        self,
        report_id: str,
        section_id: str,
        summary: str,
    ) -> None:
        key = self._key(report_id, section_id)
        if key not in self._sessions:
            self._sessions[key] = {
                "report_id": report_id,
                "section_id": section_id,
                "ticker": "",
                "entries": [],
                "summary": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        self._sessions[key]["summary"] = summary

    def load_session_summary(self, report_id: str, section_id: str) -> str:
        key = self._key(report_id, section_id)
        session = self._sessions.get(key)
        return session["summary"] if session else ""

    def get_prior_sessions_summaries(
        self,
        report_id: str,
        exclude_section_id: str | None = None,
    ) -> list[dict[str, str]]:
        results = []
        for key, session in self._sessions.items():
            if session["report_id"] != report_id:
                continue
            if exclude_section_id and session["section_id"] == exclude_section_id:
                continue
            if not session.get("summary"):
                continue
            results.append({
                "section_id": session["section_id"],
                "summary": session["summary"],
            })
        # Sort by created_at
        results.sort(key=lambda x: self._sessions.get(f"{report_id}:{x['section_id']}", {}).get("created_at", ""))
        return results
