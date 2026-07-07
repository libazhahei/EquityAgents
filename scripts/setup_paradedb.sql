-- ParadeDB pg_search + pgvector setup for RAG hybrid retrieval.
-- Prerequisites: install ParadeDB extension binaries for your Postgres version.
--   https://github.com/paradedb/paradedb/releases
--
-- Run against your database, e.g.:
--   docker compose exec postgres psql -U postgres -d tradingagents_equity -f /docker-entrypoint-initdb.d/10-setup-paradedb.sql

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_search;
