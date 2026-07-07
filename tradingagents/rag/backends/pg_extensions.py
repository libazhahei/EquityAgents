"""PostgreSQL extension / ParadeDB status helpers."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def _mask_postgres_url(url: str) -> str:
    """Hide password in connection URL for display."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


def get_extension_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """
    Inspect the database referenced by config for pgvector / pg_search / ParadeDB.

    Returns a dict suitable for printing in CLI tools.
    """
    from tradingagents.equity_research.storage.db import get_postgres_url, get_engine
    from sqlalchemy import text as sql_text

    url = get_postgres_url(config)
    parsed = urlparse(url.replace("postgresql+psycopg", "postgresql"))
    status: dict[str, Any] = {
        "postgres_url": _mask_postgres_url(url),
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/").lstrip("/") or "postgres",
        "user": parsed.username or "",
        "connected": False,
        "extensions": [],
        "vector": False,
        "pg_search": False,
        "paradedb_schema": False,
        "hybrid_search_ready": False,
        "error": None,
    }
    try:
        engine = get_engine(config)
        with engine.connect() as conn:
            status["connected"] = True
            rows = conn.execute(
                sql_text(
                    "SELECT extname, extversion FROM pg_extension "
                    "WHERE extname IN ('vector', 'pg_search') ORDER BY extname"
                )
            ).fetchall()
            status["extensions"] = [
                {"name": row[0], "version": row[1]} for row in rows
            ]
            status["vector"] = any(e["name"] == "vector" for e in status["extensions"])
            status["pg_search"] = any(e["name"] == "pg_search" for e in status["extensions"])
            schema_row = conn.execute(
                sql_text(
                    "SELECT 1 FROM pg_namespace WHERE nspname = 'paradedb' LIMIT 1"
                )
            ).first()
            status["paradedb_schema"] = schema_row is not None
            status["hybrid_search_ready"] = (
                status["vector"] and status["pg_search"] and status["paradedb_schema"]
            )
    except Exception as exc:
        status["error"] = str(exc)
    return status


def check_docker_paradedb_status(
    container: str = "tradingagents-postgres-1",
    database: str = "tradingagents_equity",
    user: str = "postgres",
) -> dict[str, Any] | None:
    """
    Query extensions inside a Docker Postgres container via ``docker exec``.

    Returns None if docker is unavailable.
    """
    import shutil
    import subprocess

    if not shutil.which("docker"):
        return None
    try:
        proc = subprocess.run(
            [
                "docker", "exec", container,
                "psql", "-U", user, "-d", database, "-tAc",
                "SELECT extname || ' ' || extversion FROM pg_extension "
                "WHERE extname IN ('vector','pg_search') ORDER BY 1",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return {
                "container": container,
                "database": database,
                "connected": False,
                "error": (proc.stderr or proc.stdout or "").strip(),
            }
        extensions = []
        for line in proc.stdout.strip().splitlines():
            parts = line.strip().split(None, 1)
            if parts:
                extensions.append(
                    {"name": parts[0], "version": parts[1] if len(parts) > 1 else ""}
                )
        schema_proc = subprocess.run(
            [
                "docker", "exec", container,
                "psql", "-U", user, "-d", database, "-tAc",
                "SELECT 1 FROM pg_namespace WHERE nspname='paradedb'",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        has_paradedb = schema_proc.stdout.strip() == "1"
        has_vector = any(e["name"] == "vector" for e in extensions)
        has_pg_search = any(e["name"] == "pg_search" for e in extensions)
        return {
            "container": container,
            "database": database,
            "connected": True,
            "extensions": extensions,
            "vector": has_vector,
            "pg_search": has_pg_search,
            "paradedb_schema": has_paradedb,
            "hybrid_search_ready": has_vector and has_pg_search and has_paradedb,
        }
    except Exception as exc:
        return {"container": container, "connected": False, "error": str(exc)}


def format_extension_status(status: dict[str, Any]) -> str:
    """Human-readable summary for the app DB connection."""
    lines = [
        "── PostgreSQL / extensions (app connection) ──",
        f"  URL:      {status.get('postgres_url', '?')}",
        f"  Host:     {status.get('host')}:{status.get('port')}",
        f"  Database: {status.get('database')}",
        f"  User:     {status.get('user') or '(default)'}",
    ]
    if status.get("error"):
        lines.append(f"  Connected: NO — {status['error']}")
        return "\n".join(lines)

    lines.append("  Connected: YES")
    exts = status.get("extensions") or []
    if exts:
        for ext in exts:
            lines.append(f"  - {ext['name']} {ext.get('version', '')}")
    else:
        lines.append("  - (no vector / pg_search extensions found)")

    lines.append(f"  pgvector:        {'yes' if status.get('vector') else 'NO'}")
    lines.append(f"  pg_search:       {'yes' if status.get('pg_search') else 'NO'}")
    lines.append(f"  paradedb schema: {'yes' if status.get('paradedb_schema') else 'NO'}")
    lines.append(
        f"  hybrid BM25+vec: {'READY' if status.get('hybrid_search_ready') else 'NOT READY'}"
    )
    if not status.get("hybrid_search_ready"):
        lines.append("  Hint: point TRADINGAGENTS_POSTGRES_URL at Docker ParadeDB, e.g.")
        lines.append(
            "        postgresql+psycopg://postgres:postgres@localhost:5432/tradingagents_equity"
        )
        lines.append("        docker compose up -d postgres")
        lines.append(
            "        docker compose exec postgres psql -U postgres -d tradingagents_equity \\"
        )
        lines.append(
            "          -f /docker-entrypoint-initdb.d/10-setup-paradedb.sql"
        )
    return "\n".join(lines)


def format_docker_extension_status(status: dict[str, Any] | None) -> str:
    if status is None:
        return "── Docker ParadeDB ──\n  (docker CLI not available)"
    lines = [
        f"── Docker ParadeDB ({status.get('container', '?')}) ──",
        f"  Database: {status.get('database', '?')}",
    ]
    if status.get("error"):
        lines.append(f"  Connected: NO — {status['error']}")
        return "\n".join(lines)
    if not status.get("connected"):
        lines.append("  Connected: NO")
        return "\n".join(lines)
    lines.append("  Connected: YES")
    exts = status.get("extensions") or []
    if exts:
        for ext in exts:
            lines.append(f"  - {ext['name']} {ext.get('version', '')}")
    else:
        lines.append("  - (no extensions — run setup_paradedb.sql)")
    lines.append(f"  pgvector:        {'yes' if status.get('vector') else 'NO'}")
    lines.append(f"  pg_search:       {'yes' if status.get('pg_search') else 'NO'}")
    lines.append(f"  paradedb schema: {'yes' if status.get('paradedb_schema') else 'NO'}")
    lines.append(
        f"  hybrid BM25+vec: {'READY' if status.get('hybrid_search_ready') else 'NOT READY'}"
    )
    return "\n".join(lines)
