# RAG Module Architecture

The `tradingagents/rag/` package provides a standalone retrieval layer decoupled from equity-research business logic.

## Pipeline

```
CorpusLoader.load(scope)
  → ChunkingStrategy.chunk(text, metadata)
  → RAGService metadata enrichment + validation
  → Embedder.embed_batch(texts)
  → IndexBackend.upsert_chunks(table, chunks, embeddings)
```

Search:

```
SearchQuery(keywords, filters)
  → IndexBackend.lexical_search (ParadeDB BM25)
  → IndexBackend.vector_search (pgvector)
  → FusionStrategy.fuse (RRF)
  → stage-2 post-processing (optional): rerank + dedupe + group diversity + recency bias
  → trim to max_chars
```

## Extension Points

| Protocol | Purpose | Register via |
|----------|---------|--------------|
| `ChunkingStrategy` | Split documents into chunks | `CorpusDefinition.chunker` or `rag.chunking.get_chunker(name)` |
| `CorpusLoader` | Load raw documents for a scope | `CorpusDefinition.loader` |
| `IndexBackend` | Persist and search chunks | `RAGService` constructor |
| `FusionStrategy` | Merge lexical + vector rankings | `HybridRetriever` / `ParadeDBHybridBackend` |
| `Embedder` | Text → vector | `EmbeddingClientAdapter` |

## Built-in Chunkers

- `paragraph` — paragraph split with word overlap
- `fixed` — fixed character windows
- `sec_item` — SEC Item section tagging + MD&A subsection tagging (`gross_profit_and_gross_margin`, `revenue`, `operating_expenses`, `liquidity`, `critical_accounting_estimates`)
- `passthrough` — one chunk per document (evidence excerpts)

## Equity Research Corpora

Registered in `tradingagents/equity_research/rag/__init__.py`:

| corpus_id | Table | Loader |
|-----------|-------|--------|
| `sec_filings` | `filing_chunk` | `SecFilingsCorpus` |
| `evidence` | `evidence_fragment` | `EvidenceCorpus` |

## SEC Filing Metadata Model

`filing_chunk` includes core retrieval metadata and quality-control metadata used by stage-2 ranking:

- Core: `ticker`, `form`, `filing_date`, `accession_number`, `section`, `chunk_index`, `chunk_text`
- Table/chunking: `chunk_type`, `table_title`, `table_section`, `parent_labels`
- Subsection/quality: `subsection_title`, `subsection_key`, `word_count`, `info_score_seed`, `content_hash`

During SEC ingest, chunks are enriched and validated before indexing. Chunks missing required metadata are skipped and recorded as structured errors.

## Usage

```python
from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.rag.types import SearchQuery, CorpusScope

deps = EquityResearchDeps(config=config, deep_llm=llm, quick_llm=llm)

# Ingest (also runs during prefetch_sec_filings)
deps.rag.ingest("sec_filings", CorpusScope(ticker="AAPL"))

# Search
result = deps.rag.search(
    "sec_filings",
    SearchQuery(keywords="data center revenue", filters={"ticker": "AAPL"}),
)
```

Tool-level SEC filing search (recommended for production answers) adds deterministic post-processing:

```python
from tradingagents.equity_research.tools.filings_rag_tools import filings_search_rag

result = filings_search_rag(
    deps,
    "NVDA",
    "gross margin recent quarters",
    section="mda",
    top_k=8,
    dedupe=True,
    rerank=True,
    prefer_recent=None,   # auto-detect from query if None
    max_per_group=2,
)
```

## PostgreSQL Setup

```bash
docker compose exec postgres psql -U postgres -d tradingagents_equity -f /docker-entrypoint-initdb.d/10-setup-paradedb.sql
```

Requires ParadeDB `pg_search` extension for BM25. pgvector is used for semantic search. Tables and BM25 indexes are created by `init_db()`.

## Operational Scripts

- Rebuild and reingest SEC index (default `NVDA`, years `2024,2025,2026`, forms `10-K,10-Q`):

```bash
uv run python scripts/ingest_sec_filings.py --rebuild-sec-index
```

- Manual ingestion for explicit ticker/year:

```bash
uv run python scripts/ingest_sec_filings.py NVDA 2025 --forms 10-K,10-Q --force
```

- Debug retrieval with stage-2 controls:

```bash
uv run python scripts/search_sec_filings.py NVDA "gross margin" --section mda --dedupe --rerank
```

- Run evaluation harness for baseline quality checks:

```bash
uv run python scripts/evaluate_sec_rag.py NVDA --json
```

## Configuration (`equity_research` block)

| Key | Default | Description |
|-----|---------|-------------|
| `sec_filing_chunker` | `sec_item` | Chunker for SEC filings |
| `filing_chunk_size` | 300 | Target words per chunk |
| `filing_chunk_overlap` | 100 | Overlap words |
| `table_rows_per_chunk` | 12 | Table rows per table chunk |
| `table_row_overlap` | 2 | Overlap rows between table chunks |
| `table_context_paragraphs` | 2 | Pre-table context paragraphs attached to table chunks |
| `rag_search_top_k` | 8 | Default hits |
| `rag_search_max_chars` | 16000 | Max returned text |
| `rag_rrf_k` | 60 | RRF constant |
| `rag_search_pool_k` | 30 | Per-channel candidate pool |
