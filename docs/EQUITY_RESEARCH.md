# Deep Equity Research (MVP1)

> Optional feature alongside the main TradingAgents trading workflow.  
> Implements hypothesis-driven mini equity research reports per `design.md` §15.1.

## Overview

`EquityResearchGraph` runs a LangGraph pipeline that:

1. Discovers market consensus and expectation gaps
2. Generates and scores investment hypotheses per report section
3. Retrieves evidence (Perplexity Search API, EDGAR filings, yfinance)
4. Extracts structured facts and verifies claims
5. Produces simplified EPS forecast and mock PE valuation
6. Writes six report sections and assembles a final mini report

### MVP1 Report Sections

| Section | ID |
|---------|-----|
| 公司简介 | `2_company_overview` |
| 行业竞争 | `3_industry_and_competition` |
| 盈利预测（简化） | `5_earnings_forecast` |
| 估值（mock） | `6_valuation` |
| 风险提示 | `7_risks` |
| 投资聚焦 | `1_investment_focus` |

## Quick Start

### 1. Install optional dependencies

```bash
pip install "tradingagents[equity-research]"
```

### 2. Configure PostgreSQL + pgvector + Redis

```bash
# Create database
createdb tradingagents_equity

# Enable pgvector
psql -d tradingagents_equity -f scripts/setup_pgvector.sql
```

Environment variables:

| Variable | Purpose |
|----------|---------|
| `TRADINGAGENTS_POSTGRES_URL` | PostgreSQL connection string |
| `TRADINGAGENTS_REDIS_URL` | Redis URL (rate limit + budget) |
| `PERPLEXITY_API_KEY` | Perplexity Search API |
| `SEC_EDGAR_USER_AGENT` | SEC EDGAR user agent (email) |
| `TRADINGAGENTS_LLM_PROVIDER` | LLM provider (shared with trading graph) |

### 3. Run via Python API

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research import EquityResearchGraph

config = DEFAULT_CONFIG.copy()
graph = EquityResearchGraph(debug=True, config=config)
final_state, summary = graph.propagate("NVDA")

print(final_state["rating"], final_state["target_price"])
print(final_state["final_report"])
```

Or use the example script:

```bash
python examples/equity_research_main.py
```

## Architecture

```
tradingagents/equity_research/
├── graph/           # EquityResearchGraph, setup, routers
├── agents/          # LangGraph node factories
├── state/           # EquityResearchState, Pydantic schemas
├── storage/         # PostgreSQL + in-memory fallback
├── integrations/    # Perplexity, EDGAR, embeddings, Redis
├── computation/     # Forecast + valuation mock
├── templates/       # MVP1 section constraints
└── export/          # Markdown memory export
```

Outputs are written to:

```
~/.tradingagents/equity_research/<TICKER>/<report_id>/
├── research_memory.md
├── full_state.json
└── full_states_log_<date>.json
```

## Design Constraints (MVP1)

- Valuation uses **mock PE multiples** — not a full DCF model
- Charts are **placeholders** (title, axes, data source, method)
- Perplexity Finance Search is used only for IC review verification
- Claims without `doc_id` evidence cannot be `verified`
- Unsupported recommendation claims block IC approval

## Testing

```bash
# Unit tests (no external services)
pytest tests/equity_research/ -m "not integration"

# Integration tests (requires PostgreSQL)
TRADINGAGENTS_POSTGRES_URL=postgresql+psycopg://... pytest tests/equity_research/test_storage_pg.py
```

## In-Memory Fallback

Set `equity_research_use_memory=True` in config to run without PostgreSQL/Redis (used in tests and local smoke runs).
