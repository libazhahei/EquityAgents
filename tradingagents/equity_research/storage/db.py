"""SQLAlchemy engine and ORM models for equity research persistence."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Default embedding dimension – kept in sync with default_config.py
EMBEDDING_DIM = 1536

_engine = None
_SessionLocal = None


class Base(DeclarativeBase):
    pass


class DocumentRegistryRow(Base):
    __tablename__ = "document_registry"

    doc_id = Column(String, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False)
    title = Column(Text)
    published_date = Column(Date)
    fiscal_period = Column(String)
    source_url = Column(Text)
    retrieved_at = Column(DateTime, default=datetime.utcnow)
    file_hash = Column(String)
    access_path = Column(Text)
    doc_fingerprint = Column(String, unique=True)
    processing_status = Column(String, default="registered")
    created_at = Column(DateTime, default=datetime.utcnow)
    reliability_score = Column(Float, default=0.5)
    citation_count = Column(Integer, default=0)
    last_used_at = Column(DateTime, nullable=True)


class LedgerEntryRow(Base):
    __tablename__ = "ledger_entry"

    entry_id = Column(String, primary_key=True)
    report_id = Column(String, index=True)
    ticker = Column(String, index=True)
    ledger_type = Column(String, nullable=False, index=True)
    payload = Column(JSON)
    created_by = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class FilingChunkRow(Base):
    __tablename__ = "filing_chunk"

    chunk_id = Column(String, primary_key=True)
    doc_id = Column(String, index=True)
    ticker = Column(String, nullable=False, index=True)
    form = Column(String, index=True)
    filing_date = Column(Date)
    accession_number = Column(String, index=True)
    section = Column(String, index=True)
    chunk_index = Column(Integer, default=0)
    chunk_text = Column(Text, nullable=False)
    source_url = Column(Text)
    doc_key = Column(String, index=True)
    chunk_type = Column(String, default="text", index=True)  # "text" or "table"
    table_title = Column(String)  # Title for table chunks
    table_section = Column(String)  # Section context for table chunks
    parent_labels = Column(JSON)  # Hierarchical parent labels for table chunks
    subsection_title = Column(String, index=True)
    subsection_key = Column(String, index=True)
    word_count = Column(Integer)
    info_score_seed = Column(Float)
    content_hash = Column(String(64), index=True)
    year = Column(String)  # e.g. "FY2024"
    quarter = Column(String)  # e.g. "Q1", "Q2", "Q3", "Q4"
    created_at = Column(DateTime, default=datetime.utcnow)


class EvidenceFragmentRow(Base):
    __tablename__ = "evidence_fragment"

    fragment_id = Column(String, primary_key=True)
    doc_id = Column(String, index=True)
    ticker = Column(String, nullable=False, index=True)
    section_in_source = Column(String)
    page_number = Column(Integer)
    paragraph_index = Column(Integer)
    excerpt_text = Column(Text, nullable=False)
    excerpt_context = Column(Text)
    extracted_by_task_id = Column(String)
    extraction_confidence = Column(Float)
    fragment_type = Column(String)
    source_reliability = Column(String, default="medium")
    hypothesis_id = Column(String)
    embedding = Column(Text)  # stored as pgvector literal when extension available
    created_at = Column(DateTime, default=datetime.utcnow)


class StructuredFactRow(Base):
    __tablename__ = "structured_fact"

    fact_id = Column(String, primary_key=True)
    ticker = Column(String, nullable=False, index=True)
    metric_name = Column(String, nullable=False)
    metric_value = Column(Float)
    metric_value_text = Column(Text)
    unit = Column(String)
    fiscal_period = Column(String)
    segment = Column(String)
    source_doc_id = Column(String)
    extraction_confidence = Column(Float)
    data_version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class ResearchTraceRow(Base):
    __tablename__ = "research_trace"

    trace_id = Column(String, primary_key=True)
    report_id = Column(String, index=True)
    ticker = Column(String, index=True)
    node_name = Column(String)
    hypothesis_id = Column(String)
    section_id = Column(String)
    payload = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)


def get_postgres_url(config: dict[str, Any] | None = None) -> str:
    if config and config.get("postgres_url"):
        return config["postgres_url"]
    return os.environ.get(
        "TRADINGAGENTS_POSTGRES_URL",
        "postgresql+psycopg://localhost/tradingagents_equity",
    )


def get_embedding_dim(config: dict[str, Any] | None = None) -> int:
    """Return the embedding dimension from config, falling back to EMBEDDING_DIM."""
    if config:
        er = config.get("equity_research", {})
        dim = er.get("embedding_dim")
        if dim is not None:
            return int(dim)
    return EMBEDDING_DIM


def get_engine(config: dict[str, Any] | None = None):
    global _engine, _SessionLocal
    if _engine is None:
        url = get_postgres_url(config)
        _engine = create_engine(url, pool_pre_ping=True)
        _SessionLocal = sessionmaker(bind=_engine)
    return _engine


def get_session(config: dict[str, Any] | None = None) -> Session:
    get_engine(config)
    return _SessionLocal()


def drop_tables(config: dict[str, Any] | None = None, *, tables: list[str] | None = None) -> None:
    """Drop specified tables (or all managed tables if *tables* is None).

    This is useful when the schema has changed (e.g. embedding dimension
    changed) and tables need to be recreated from scratch.
    """
    engine = get_engine(config)
    all_tables = [
        "filing_chunk",
        "evidence_fragment",
        "structured_fact",
        "research_trace",
        "document_registry",
        "ledger_entry",
    ]
    to_drop = tables or all_tables
    with engine.connect() as conn:
        for tbl in to_drop:
            try:
                conn.execute(text(f"DROP TABLE IF EXISTS {tbl} CASCADE"))
                logger.info("Dropped table %s", tbl)
            except Exception as exc:
                logger.warning("Failed to drop table %s: %s", tbl, exc)
        conn.commit()


import logging
logger = logging.getLogger(__name__)


def init_db(config: dict[str, Any] | None = None) -> None:
    """Create tables and pgvector extension if available."""
    engine = get_engine(config)
    dim = get_embedding_dim(config)
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        except Exception:
            conn.rollback()
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_search"))
            conn.commit()
        except Exception:
            conn.rollback()
    Base.metadata.create_all(engine)
    _ensure_vector_column(engine, dim)
    _ensure_filing_chunk_vector_column(engine, dim)
    _ensure_filing_chunk_table_columns(engine)
    _ensure_document_registry_columns(engine)
    _ensure_bm25_indexes(engine)


def _ensure_vector_column(engine, dim: int) -> None:
    with engine.connect() as conn:
        try:
            # Check if column exists and has correct dimension
            row = conn.execute(
                text(
                    "SELECT udt_name, character_maximum_length "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'evidence_fragment' AND column_name = 'embedding_vec'"
                )
            ).first()
            if row is not None:
                # Column exists – check dimension
                current_dim = conn.execute(
                    text(
                        "SELECT atttypmod FROM pg_attribute "
                        "WHERE attrelid = 'evidence_fragment'::regclass AND attname = 'embedding_vec'"
                    )
                ).scalar()
                if current_dim is not None and current_dim != dim:
                    logger.warning(
                        "evidence_fragment.embedding_vec dimension mismatch "
                        "(%d vs %d); dropping and recreating",
                        current_dim, dim,
                    )
                    conn.execute(text("DROP INDEX IF EXISTS idx_evidence_embedding"))
                    conn.execute(
                        text("ALTER TABLE evidence_fragment DROP COLUMN embedding_vec")
                    )
                    conn.commit()
                    row = None  # force recreation

            if row is None:
                conn.execute(
                    text(
                        f"ALTER TABLE evidence_fragment "
                        f"ADD COLUMN IF NOT EXISTS embedding_vec vector({dim})"
                    )
                )
                conn.commit()

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_evidence_embedding
                    ON evidence_fragment USING ivfflat (embedding_vec vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
            conn.commit()
        except Exception:
            conn.rollback()


def _ensure_filing_chunk_vector_column(engine, dim: int) -> None:
    with engine.connect() as conn:
        try:
            # Check if column exists and has correct dimension
            row = conn.execute(
                text(
                    "SELECT udt_name "
                    "FROM information_schema.columns "
                    "WHERE table_name = 'filing_chunk' AND column_name = 'embedding_vec'"
                )
            ).first()
            if row is not None:
                # Column exists – check dimension via pg_attribute
                current_dim = conn.execute(
                    text(
                        "SELECT atttypmod FROM pg_attribute "
                        "WHERE attrelid = 'filing_chunk'::regclass AND attname = 'embedding_vec'"
                    )
                ).scalar()
                if current_dim is not None and current_dim != dim:
                    logger.warning(
                        "filing_chunk.embedding_vec dimension mismatch "
                        "(%d vs %d); dropping and recreating",
                        current_dim, dim,
                    )
                    conn.execute(text("DROP INDEX IF EXISTS idx_filing_chunk_embedding"))
                    conn.execute(
                        text("ALTER TABLE filing_chunk DROP COLUMN embedding_vec")
                    )
                    conn.commit()
                    row = None  # force recreation

            if row is None:
                conn.execute(
                    text(
                        f"ALTER TABLE filing_chunk "
                        f"ADD COLUMN IF NOT EXISTS embedding_vec vector({dim})"
                    )
                )
                conn.commit()

            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_filing_chunk_embedding
                    ON filing_chunk USING ivfflat (embedding_vec vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
            conn.commit()
        except Exception:
            conn.rollback()




def _ensure_filing_chunk_table_columns(engine) -> None:
    """Add optional filing_chunk metadata columns used by retrieval quality controls."""
    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS chunk_type VARCHAR(50) DEFAULT 'text'
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS table_title VARCHAR(500)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS table_section VARCHAR(100)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS parent_labels JSONB
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS subsection_title VARCHAR(500)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS subsection_key VARCHAR(200)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS word_count INTEGER
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS info_score_seed DOUBLE PRECISION
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64)
                    """
                )
            )
            # Year/quarter filters for SEC filings
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS year VARCHAR(20)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE filing_chunk
                    ADD COLUMN IF NOT EXISTS quarter VARCHAR(10)
                    """
                )
            )
            # Add index for chunk_type filtering
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_filing_chunk_type
                    ON filing_chunk (chunk_type)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_filing_chunk_subsection
                    ON filing_chunk (subsection_key)
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_filing_chunk_content_hash
                    ON filing_chunk (content_hash)
                    """
                )
            )
            conn.commit()
        except Exception:
            conn.rollback()


def _ensure_bm25_indexes(engine) -> None:
    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_filing_chunk_bm25
                    ON filing_chunk
                    USING bm25 (chunk_id, chunk_text, ticker, form, section)
                    WITH (key_field='chunk_id')
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS idx_evidence_fragment_bm25
                    ON evidence_fragment
                    USING bm25 (fragment_id, excerpt_text, ticker, fragment_type)
                    WITH (key_field='fragment_id')
                    """
                )
            )
            conn.commit()
        except Exception:
            conn.rollback()


def _ensure_document_registry_columns(engine) -> None:
    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    """
                    ALTER TABLE document_registry
                    ADD COLUMN IF NOT EXISTS reliability_score DOUBLE PRECISION DEFAULT 0.5
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE document_registry
                    ADD COLUMN IF NOT EXISTS citation_count INTEGER DEFAULT 0
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE document_registry
                    ADD COLUMN IF NOT EXISTS last_used_at TIMESTAMP
                    """
                )
            )
            conn.commit()
        except Exception:
            conn.rollback()
