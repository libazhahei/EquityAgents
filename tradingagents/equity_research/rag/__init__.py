"""Register equity-research corpora with the RAG registry."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.rag.evidence import EvidenceCorpus
from tradingagents.equity_research.rag.sec_filings import SecFilingsCorpus
from tradingagents.rag.corpora.base import CorpusDefinition
from tradingagents.rag.registry import CorpusRegistry


def register_equity_corpora(
    registry: CorpusRegistry,
    config: dict[str, Any],
    *,
    edgar: Any | None = None,
    evidence_store: Any | None = None,
) -> None:
    er = config.get("equity_research", {})
    sec_chunker = er.get("sec_filing_chunker", "sec_item")

    registry.register(
        CorpusDefinition(
            corpus_id="sec_filings",
            table_name="filing_chunk",
            loader=SecFilingsCorpus(config, edgar=edgar),
            chunker=sec_chunker,
            doc_key_column="accession_number",
            filter_columns=("ticker", "form", "section"),
        )
    )
    registry.register(
        CorpusDefinition(
            corpus_id="evidence",
            table_name="evidence_fragment",
            loader=EvidenceCorpus(config, evidence_store=evidence_store),
            chunker="passthrough",
            text_column="excerpt_text",
            id_column="fragment_id",
            doc_key_column="fragment_id",
            filter_columns=("ticker", "hypothesis_id", "fragment_type"),
            schema={"json_embedding": True},
        )
    )
