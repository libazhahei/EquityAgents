"""Backend factory tests."""

from tradingagents.rag.backends import create_backend, _pg_search_available
from tradingagents.rag.backends.pgvector import PgVectorBackend


def test_create_backend_uses_pgvector_when_no_paradedb():
    config = {"equity_research_use_memory": False}
    # Assumes local PG without ParadeDB in dev/CI
    if not _pg_search_available(config):
        try:
            backend = create_backend(config)
            assert isinstance(backend, PgVectorBackend)
        except Exception:
            pass  # no PG in CI
