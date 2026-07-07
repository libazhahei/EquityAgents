"""Index backend exports."""

from tradingagents.rag.backends.in_memory import InMemoryBackend
from tradingagents.rag.backends.paradedb import ParadeDBHybridBackend
from tradingagents.rag.backends.pgvector import PgVectorBackend

__all__ = ["InMemoryBackend", "PgVectorBackend", "ParadeDBHybridBackend"]


def _pg_search_available(config: dict) -> bool:
    try:
        from tradingagents.equity_research.storage.db import get_engine
        from sqlalchemy import text as sql_text

        engine = get_engine(config)
        with engine.connect() as conn:
            ext = conn.execute(
                sql_text("SELECT 1 FROM pg_extension WHERE extname = 'pg_search' LIMIT 1")
            ).first()
            if ext is None:
                return False
            schema = conn.execute(
                sql_text("SELECT 1 FROM pg_namespace WHERE nspname = 'paradedb' LIMIT 1")
            ).first()
            return schema is not None
    except Exception:
        return False


def create_backend(config: dict, *, use_memory: bool = False):
    if use_memory or config.get("equity_research_use_memory"):
        return InMemoryBackend(config)
    try:
        from tradingagents.equity_research.storage.db import get_engine
        from sqlalchemy import text as sql_text

        engine = get_engine(config)
        with engine.connect() as conn:
            conn.execute(sql_text("SELECT 1"))
        if _pg_search_available(config):
            return ParadeDBHybridBackend(config)
        return PgVectorBackend(config)
    except Exception:
        return InMemoryBackend(config)
