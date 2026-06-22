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

# Default embedding dimension (Qwen text-embedding-v3 / OpenAI ada-002 compatible)
EMBEDDING_DIM = 1024

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


def init_db(config: dict[str, Any] | None = None) -> None:
    """Create tables and pgvector extension if available."""
    engine = get_engine(config)
    with engine.connect() as conn:
        try:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()
        except Exception:
            conn.rollback()
    Base.metadata.create_all(engine)
    _ensure_vector_column(engine)


def _ensure_vector_column(engine) -> None:
    with engine.connect() as conn:
        try:
            conn.execute(
                text(
                    f"""
                    ALTER TABLE evidence_fragment
                    ADD COLUMN IF NOT EXISTS embedding_vec vector({EMBEDDING_DIM})
                    """
                )
            )
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
