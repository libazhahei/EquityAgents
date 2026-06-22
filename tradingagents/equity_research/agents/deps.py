"""Shared dependencies injected into equity research agent nodes."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from tradingagents.equity_research.integrations.edgar import EdgarClient
from tradingagents.equity_research.integrations.embeddings import EmbeddingClient
from tradingagents.equity_research.integrations.info_sources import InfoSourceRegistry, default_registry
from tradingagents.equity_research.integrations.perplexity import PerplexityClient
from tradingagents.equity_research.integrations.redis_cache import RedisClient
from tradingagents.equity_research.storage.document_registry import DocumentRegistry
from tradingagents.equity_research.storage.evidence_store import EvidenceStore
from tradingagents.equity_research.storage.fact_store import FactStore
from tradingagents.equity_research.storage.in_memory import (
    InMemoryDocumentRegistry,
    InMemoryEvidenceStore,
    InMemoryFactStore,
    InMemoryTraceStore,
)
from tradingagents.equity_research.storage.trace_store import TraceStore

logger = logging.getLogger(__name__)


def _try_postgres_store(factory, in_memory_factory, config):
    if config.get("equity_research_use_memory"):
        return in_memory_factory()
    try:
        from tradingagents.equity_research.storage.db import get_engine
        engine = get_engine(config)
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return factory(config)
    except Exception as exc:
        logger.warning("PostgreSQL storage unavailable (%s); using in-memory fallback", exc)
        return in_memory_factory()


@dataclass
class EquityResearchDeps:
    config: dict[str, Any]
    deep_llm: Any
    quick_llm: Any
    documents: Any = None
    evidence: Any = None
    facts: Any = None
    traces: Any = None
    perplexity: PerplexityClient = field(default_factory=lambda: PerplexityClient())
    edgar: EdgarClient = field(default_factory=lambda: EdgarClient())
    embeddings: EmbeddingClient = field(default_factory=lambda: EmbeddingClient())
    redis: RedisClient = field(default_factory=lambda: RedisClient())
    info_sources: InfoSourceRegistry = field(default_factory=default_registry)
    _use_memory: bool = False

    def __post_init__(self):
        if self.config.get("equity_research_use_memory"):
            self._use_memory = True
        if self._use_memory:
            self.documents = InMemoryDocumentRegistry()
            self.evidence = InMemoryEvidenceStore()
            self.facts = InMemoryFactStore()
            self.traces = InMemoryTraceStore()
        else:
            self.documents = _try_postgres_store(DocumentRegistry, InMemoryDocumentRegistry, self.config)
            self.evidence = _try_postgres_store(EvidenceStore, InMemoryEvidenceStore, self.config)
            self.facts = _try_postgres_store(FactStore, InMemoryFactStore, self.config)
            self.traces = _try_postgres_store(TraceStore, InMemoryTraceStore, self.config)
        self.perplexity = PerplexityClient(self.config)
        self.edgar = EdgarClient(self.config)
        self.embeddings = EmbeddingClient(self.config)
        redis_cfg = {**self.config, "equity_research_use_memory": self._use_memory}
        self.redis = RedisClient(redis_cfg)

    def trace(self, state: dict, node_name: str, payload: dict | None = None) -> dict:
        entry = self.traces.append(
            report_id=state.get("report_id", ""),
            ticker=state.get("ticker", ""),
            node_name=node_name,
            payload=payload or {},
            hypothesis_id=state.get("active_hypothesis_ids", [None])[0] if state.get("active_hypothesis_ids") else None,
            section_id=state.get("active_section_id"),
        )
        traces = list(state.get("research_traces", []))
        traces.append(entry)
        return {
            "research_traces": traces,
            "last_updated": datetime.utcnow().isoformat(),
        }
