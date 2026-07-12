"""LangGraph checkpoint + run-tree index for equity research.

Per-ticker SQLite DBs under ``{data_dir}/checkpoints/equity_research/<TICKER>.db``.
Thread id: ``{ticker}:{as_of_date}:{run_id}``. Nested subgraphs share the same
thread and rely on LangGraph ``checkpoint_ns``. The ``er_run_tree`` table indexes
stages for future tree UI / SSE.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langgraph.checkpoint.sqlite import SqliteSaver

from tradingagents.dataflows.utils import safe_ticker_component

_RUN_TREE_DDL = """
CREATE TABLE IF NOT EXISTS er_run_tree (
  run_id TEXT NOT NULL,
  parent_run_id TEXT,
  ticker TEXT NOT NULL,
  as_of_date TEXT NOT NULL,
  node_path TEXT NOT NULL,
  section_id TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  meta_json TEXT,
  PRIMARY KEY (run_id, node_path)
);
"""


def equity_checkpoint_db_path(data_dir: str | Path, ticker: str) -> Path:
    """Return the SQLite checkpoint DB path for a ticker."""
    safe = safe_ticker_component(ticker).upper()
    p = Path(data_dir) / "checkpoints" / "equity_research"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{safe}.db"


def make_thread_id(ticker: str, as_of_date: str, run_id: str) -> str:
    """Hierarchical, stable LangGraph thread id."""
    return f"{ticker.upper()}:{as_of_date}:{run_id}"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_run_tree(conn: sqlite3.Connection) -> None:
    conn.execute(_RUN_TREE_DDL)
    conn.commit()


@contextmanager
def get_equity_checkpointer(
    data_dir: str | Path,
    ticker: str,
) -> Generator[SqliteSaver, None, None]:
    """Context manager yielding a SqliteSaver backed by a per-ticker equity DB."""
    db = equity_checkpoint_db_path(data_dir, ticker)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    try:
        _ensure_run_tree(conn)
        saver = SqliteSaver(conn)
        saver.setup()
        # Expose connection for run-tree helpers without a second open.
        saver._er_conn = conn  # type: ignore[attr-defined]
        yield saver
    finally:
        conn.close()


def _conn_from_saver(saver: SqliteSaver) -> sqlite3.Connection:
    conn = getattr(saver, "_er_conn", None)
    if conn is None:
        raise RuntimeError("SqliteSaver was not created via get_equity_checkpointer")
    return conn


def register_run(
    saver: SqliteSaver,
    *,
    run_id: str,
    ticker: str,
    as_of_date: str,
    parent_run_id: str | None = None,
    status: str = "running",
) -> None:
    """Register the root edge for a research run."""
    upsert_run_edge(
        saver,
        run_id=run_id,
        ticker=ticker,
        as_of_date=as_of_date,
        node_path="root",
        parent_run_id=parent_run_id,
        status=status,
    )


def upsert_run_edge(
    saver: SqliteSaver,
    *,
    run_id: str,
    ticker: str,
    as_of_date: str,
    node_path: str,
    parent_run_id: str | None = None,
    section_id: str | None = None,
    status: str = "running",
    meta: dict[str, Any] | None = None,
) -> None:
    """Insert or update a run-tree edge for a stage / section."""
    conn = _conn_from_saver(saver)
    _ensure_run_tree(conn)
    now = _utcnow()
    meta_json = json.dumps(meta or {}, default=str)
    conn.execute(
        """
        INSERT INTO er_run_tree (
            run_id, parent_run_id, ticker, as_of_date, node_path, section_id,
            status, created_at, updated_at, meta_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id, node_path) DO UPDATE SET
            parent_run_id=excluded.parent_run_id,
            section_id=excluded.section_id,
            status=excluded.status,
            updated_at=excluded.updated_at,
            meta_json=excluded.meta_json
        """,
        (
            run_id,
            parent_run_id,
            ticker.upper(),
            as_of_date,
            node_path,
            section_id,
            status,
            now,
            now,
            meta_json,
        ),
    )
    conn.commit()


def list_run_tree(
    data_dir: str | Path,
    ticker: str,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """List run-tree rows for a ticker (optionally filtered by run_id)."""
    db = equity_checkpoint_db_path(data_dir, ticker)
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db))
    try:
        _ensure_run_tree(conn)
        if run_id:
            rows = conn.execute(
                "SELECT * FROM er_run_tree WHERE ticker = ? AND run_id = ? ORDER BY created_at",
                (ticker.upper(), run_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM er_run_tree WHERE ticker = ? ORDER BY created_at",
                (ticker.upper(),),
            ).fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM er_run_tree LIMIT 0").description]
        results: list[dict[str, Any]] = []
        for row in rows:
            item = dict(zip(cols, row))
            raw = item.pop("meta_json", None)
            try:
                item["meta"] = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                item["meta"] = {}
            results.append(item)
        return results
    finally:
        conn.close()


def clear_equity_checkpoint(data_dir: str | Path, ticker: str, thread_id: str) -> None:
    """Remove LangGraph checkpoint rows for a thread_id (keeps run-tree history)."""
    db = equity_checkpoint_db_path(data_dir, ticker)
    if not db.exists():
        return
    conn = sqlite3.connect(str(db))
    try:
        for table in ("writes", "checkpoints"):
            try:
                conn.execute(f"DELETE FROM {table} WHERE thread_id = ?", (thread_id,))
            except sqlite3.OperationalError:
                pass
        conn.commit()
    finally:
        conn.close()
