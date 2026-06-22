-- One-time setup for Deep Equity Research pgvector support.
-- Run against your PostgreSQL database, e.g.:
--   psql -d tradingagents_equity -f scripts/setup_pgvector.sql

CREATE EXTENSION IF NOT EXISTS vector;
