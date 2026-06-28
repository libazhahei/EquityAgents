# Equity R&D-Agent

> Optional feature alongside the main TradingAgents trading workflow.  
> Evolved from the earlier Hybrid Equity Research spine into an R&D-Agent research paradigm.

## Overview

`EquityResearchGraph` implements an **Equity R&D-Agent**:

```text
Research Phase   →  thesis graph exploration, evidence, Quick Diligence
Development Phase →  modeling, valuation, section artifacts
Evaluation Phase  →  aggregated scoring, IC review, Final QA
```

**Product principle:** do not let the agent generate a report in one shot. Research investment theses first, develop evidence and models, then write sections.

### Outer workflow (15 LangGraph phase nodes)

```text
initialize_state
  → analyze_research_task      # mandate, ingest, broker, consensus subgraph, gaps, init graph
                                 # consensus: see docs/equity_research/agent-loop-and-tasks.md
  → dynamic_planning           # stage-aware strategy (orientation → convergence)
  → research_loop              # inner 9-step R&D iteration
      ↺ continue_research → dynamic_planning
      → ready_for_modeling → modeling_workflow
  → valuation_workflow
  → branch_merge               # merge best thesis branches
  → risk_mapping
  → investment_committee_review
      ↺ revise_research / revise_model / revise_valuation
  → write_investment_focus     # late writing: summary after IC
  → write_remaining_sections → plan_tables_and_charts → chart_generation
  → assemble_report → final_qa → export_report
```

### Inner research loop (per iteration)

Executed inside the `research_loop` node (`agents/research_loop.py`):

| Step | Action |
|------|--------|
| ① | Dynamic planning — stage + budget allocation |
| ② | Select parent thesis nodes from `research_graph` |
| ③ | Build collaborative memory context from ledgers |
| ④ | Identify key research problems |
| ⑤ | Generate scientific investment hypotheses (5-dimension scoring) |
| ⑥ | Virtual IC — select promising branch |
| ⑦ | Quick diligence — max ~5 evidence items; reject / park / full_diligence |
| ⑧ | Full development — evidence retrieve → facts → verify → domain skills |
| ⑨ | Aggregated thesis evaluation → update `research_graph` |

Stop when `research_graph.best_node_id` score ≥ threshold, max iterations reached, or stage = `convergence`.

### Report sections (10)

| Section | ID |
|---------|-----|
| 投资摘要 | `1_investment_summary` |
| 公司简介 | `2_company_overview` |
| 商业模式 | `3_business_model` |
| 行业竞争 | `4_industry_and_competition` |
| 历史财务 | `5_historical_financials` |
| 盈利预测 | `6_earnings_forecast` |
| 估值分析 | `7_valuation` |
| 情景敏感性 | `8_scenario_and_sensitivity` |
| 风险与反证 | `9_risks` |
| 附录 | `10_appendix` |

Investment summary is written **last** (after IC review), but displayed **first** in the final report.

## Quick Start

### 1. Install optional dependencies

```bash
pip install "tradingagents[equity-research]"
```

### 2. Configure PostgreSQL + pgvector + Redis

```bash
createdb tradingagents_equity
psql -d tradingagents_equity -f scripts/setup_pgvector.sql
```

Environment variables:

| Variable | Purpose |
|----------|---------|
| `TRADINGAGENTS_POSTGRES_URL` | PostgreSQL connection string |
| `TRADINGAGENTS_REDIS_URL` | Redis URL (rate limit + budget) |
| `PERPLEXITY_API_KEY` | Perplexity Search API |
| `SEC_EDGAR_USER_AGENT` | SEC EDGAR user agent (email) |
| `FMP_API_KEY` | Financial Modeling Prep (earnings calls only, not quotes) |
| `TRADINGAGENTS_LLM_PROVIDER` | LLM provider (shared with trading graph) |

### 3. Run via Python API

```python
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.equity_research import EquityResearchGraph

config = DEFAULT_CONFIG.copy()
graph = EquityResearchGraph(debug=True, config=config)
final_state, summary = graph.propagate("NVDA")

print(final_state["rating"], final_state["target_price"])
print(final_state["research_graph"]["best_node_id"])
print(final_state["final_report"])
```

## Architecture

```
tradingagents/equity_research/
├── graph/              # Outer LangGraph (setup.py, routers.py)
├── agents/
│   ├── research_loop.py      # Inner R&D loop runtime (thesis graph)
│   ├── task_analysis.py      # Init spine: static consensus subgraph + gaps + graph bootstrap
│   ├── consensus/            # Thin wrapper → GenericResearchSubgraph + parent state mapping
│   ├── dynamic_planning.py
│   ├── modeling_workflow.py
│   ├── valuation_workflow.py
│   ├── branch_merge.py
│   ├── risk_mapping.py
│   ├── final_qa.py
│   ├── lead_analyst.py       # Domain agent orchestrator (not Task Decomposer)
│   └── domain/               # 9 domain analyst agents (logical roles)
├── runtime/            # GenericResearchSubgraph framework (PER loop, zero business logic)
├── tasks/              # TaskProfile configs (currently: consensus)
├── skills/             # SkillRegistry + implementations
├── tools/              # ToolRegistry (data, calculators, ledgers)
├── state/
│   ├── equity_research_state.py
│   ├── research_graph.py     # Thesis exploration DAG
│   ├── ledgers.py
│   └── schemas.py
├── memory/             # Collaborative memory retrieval
├── evaluation/         # Aggregated thesis / IC scoring
├── prompts/            # rd_agent.py prompt pack
├── storage/            # PostgreSQL + in-memory fallback
├── integrations/       # Perplexity, EDGAR, FMP, embeddings, Redis
├── computation/        # Forecast + valuation engine
├── templates/          # 10-section report constraints
└── export/             # Markdown memory export
```

### Ledgers

| Ledger | Purpose |
|--------|---------|
| **Evidence** | Source-linked excerpts, reliability / freshness |
| **Claim** | Judgments linked to supporting / contradicting evidence |
| **Assumption** | Forecast and valuation assumptions with consensus bridge |
| **Consensus** | Structured market consensus entries |
| **Broker View** | Sell-side ratings, targets, summaries |
| **Forecast / Valuation** | Version history per modeling iteration |
| **Issue** | Gate rejections, blocking issues, resolution tracking |
| **Research Graph** | Thesis branches as DAG nodes with scores and artifacts |

`sync_ledgers_from_legacy()` provides bidirectional sync between legacy state fields and ledger structures. Skills/tools should prefer `write_to_ledger()` as the primary write path.

### Domain agents

Thin wrappers in `agents/domain/`, dispatched by `LeadAnalystAgent`:

| Agent | Skills |
|-------|--------|
| EvidenceAnalyst | `collaborative_memory` |
| ConsensusAnalyst | `broker_consensus_mining`, `variant_view_discovery` |
| BusinessAnalyst | `business_model_analysis` |
| IndustryAnalyst | `industry_analysis` |
| ForecastAgent | `forecast_assumption_builder` |
| ValuationAgent | `valuation` |
| RiskAgent | `risk_counterthesis` |
| ICChallenge | `standardized_qa` |
| WritingAgent | `section_writing` |

### Skills (registry)

| Skill | Purpose |
|-------|---------|
| `dynamic_research_planning` | Stage-aware planning and budget allocation |
| `thesis_exploration_dag` | Initialize thesis branches (revenue / margin / multiple / bear / FCF) |
| `scientific_investment_reasoning` | Structured hypothesis generation (delegated to research loop) |
| `collaborative_memory` | Cross-branch ledger retrieval |
| `broker_consensus_mining` | Sell-side views and consensus |
| `variant_view_discovery` | Expectation gaps / variant view |
| `business_model_analysis` | Revenue drivers and unit economics |
| `industry_analysis` | Industry and competitive landscape |
| `historical_financial_analysis` | Historical financial trends |
| `forecast_assumption_builder` | Driver → assumption ledger entries |
| `valuation` | Deterministic target price via calculators |
| `risk_counterthesis` | Risk-to-thesis mapping |
| `catalyst_monitoring` | Catalyst calendar |
| `standardized_qa` | Evidence / model / compliance scoring |
| `section_writing` | Section draft context from verified claims |

Prompt templates live in `prompts/rd_agent.py` (task analysis, planning, hypothesis, quick diligence, thesis merge, etc.).

### Evaluation

`evaluation/aggregators.py` implements weighted thesis scoring:

```text
evidence_strength (20%) + consensus_gap (20%) + financial_materiality (20%)
+ valuation_impact (15%) + catalyst_clarity (10%) + risk_adjusted (10%) + novelty (5%)
```

IC review uses `aggregate_ic_scores()` and records blocking issues to `issue_ledger`.

### 系统架构专题

以下中文文档对模块内部机制做专项说明（文件结构、Memory、Context、Skills/Tools 控制方案）：

| 文档 | 内容 |
|------|------|
| [equity_research/file-structure.md](equity_research/file-structure.md) | 完整目录树、执行流与代码入口速查 |
| [equity_research/agent-loop-and-tasks.md](equity_research/agent-loop-and-tasks.md) | GenericResearchSubgraph PER 循环、TaskProfile、Task 分配现状与规划 |
| [equity_research/memory.md](equity_research/memory.md) | Ledger 分层、读写路径、检索评分与导出 |
| [equity_research/context.md](equity_research/context.md) | Context 注入链路、预算上限与 LLM 压缩 |
| [equity_research/skills-and-tools.md](equity_research/skills-and-tools.md) | Skill/Tool 注册、可见性、绑定与发现工具 |
| [equity_research/storage.md](equity_research/storage.md) | Redis、PostgreSQL、本地文件的配置与数据流 |

## Design constraints

- Target price and EPS come from **deterministic calculators**, not LLM invention
- `7_valuation` requires `requires_model_output: True`
- Rating based on `12_month_total_return` (price upside + dividend yield)
- Claims without evidence should not reach `verified` status
- IC / Final QA can route back to `dynamic_planning`, `modeling_workflow`, or `valuation_workflow`
- FMP is used for **earnings call transcripts only**, not quote data

## Testing

```bash
pytest tests/equity_research/ -m "not integration" -q
```

Key test files:

| File | Covers |
|------|--------|
| `test_workflow_spine.py` | Outer graph node names |
| `test_research_loop.py` | Inner loop + graph updates |
| `test_research_graph.py` | Parent selection, branch merge, scoring |
| `test_memory_retrieval.py` | Collaborative memory sampling |
| `test_ledgers.py` | Ledger sync and `write_to_ledger` |
| `test_routers.py` | Conditional routing |
| `test_e2e_mini_report.py` | Full graph smoke (mocked LLM) |

## In-memory fallback

Set `equity_research_use_memory=True` in config to run without PostgreSQL/Redis.
