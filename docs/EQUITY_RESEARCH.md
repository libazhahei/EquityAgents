# Equity R&D-Agent

> **Full technical documentation:** [README.md](../README.md) (English) · [README.zh-CN.md](../README.zh-CN.md) (中文)  
> **Trading framework:** [TRADINGAGENTS.md](TRADINGAGENTS.md) · [中文版](zh/TRADINGAGENTS.md)

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


### State Machine Workflow with Human Review Gates {#human-review-gates}

The pipeline is implemented as a **multi-step state machine** — each stage validates its inputs before advancing, and key decision points expose **human review interrupt nodes** (`human_review_1` after consensus/assumption, `human_review_2` after planner). When triggered, these interrupts pause execution (with LangGraph checkpoint) so a human can review outputs and resume with patches.

| Scenario | Gate Triggered | Rework Path |
|----------|---------------|-------------|
| Insufficient research depth | `human_review_2` → patch sections | Resume `planner`, re-enter `section_research` |
| Anomalous assumptions detected | `human_review_1` → amend `assumption_view` | Resume downstream phases |
| Unreasonable valuation output | `human_review_1` → update `assumption_map` | Revise forward through pipeline |
| Report quality below threshold | `human_review_2` → adjust plan | Re-plan affected sections |

**Performance:** In local phased testing, each step in the initial end-to-end research chain takes **80–120 seconds**. The human-in-the-loop rework mechanism reduces the overall rework rate from an estimated 30%+ down to **18%** by catching issues early at structured gate points rather than post-completion.

Checkpoint/resume capability is provided via [`graph/checkpointer.py`](tradingagents/equity_research/graph/checkpointer.py): per-ticker SQLite databases under `{data_cache_dir}/checkpoints/equity_research/<TICKER>.db`, indexed by `er_run_tree`. Resuming applies any patches automatically.

#### Performance Metrics Summary

| Metric | Value | Mechanism |
|--------|-------|-----------|
| Per-step latency (initial E2E chain) | **80–120s** per outer node | Sequential stage execution with LangGraph checkpoints |
| Overall rework rate | **18%** | Human review gates (HR1/HR2) catch issues pre-write rather than post-completion |
| Invalid search paths reduced | **−32%** vs. flat exhaustive search | Branch pruning via `quick_diligence` verdicts (`reject`/`park`) + stage-aware budget allocation |
| Average token consumption per stock study | **−36%** reduction | Same branch pruning + memory pruning (`prune_stale_evidence`, `merge_similar_evidence`) |
| Context injection volume reduced | **−23%** | Memory maintenance (deduplication + staleness removal) + soft context compact (see [context.md](equity_research/context.md)) |
| Evidence HitRate@10 | **82%–88%** | BM25 + pgvector + RRF hybrid retrieval via `RAGService` (see [memory.md §2.1](equity_research/memory.md)) |
| Report conclusion evidence traceability | **~90%** | Evidence→Claim ledger chain with `related_evidence_ids` in `BlackboardEntry`; claim supports thesis statements |
| Skill–objective match rate | **~85%** | `SkillRegistry.select_for_objective()` fallback + catalog frontmatter filtering (see [skills-and-tools.md](equity_research/skills-and-tools.md)) |
| Valuation computation reproducibility | **95%** | E2B sandbox isolated Python execution (see `tools/lc/code.py`, `integrations/e2b_sandbox.py`) |

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

### 4. Run via CLI — `demo_equity_research.py`

End-to-end CLI that runs the full pipeline and writes a run bundle:

```bash
# Basic run (writes to out/<TICKER>_equity_<timestamp>/full_state.json)
uv run python demo_equity_research.py NVDA --date 2025-07-10

# With human review passthrough patches
uv run python demo_equity_research.py NVDA     --human-review-json examples/human_review_passthrough.json

# Export JSON to stdout + save bundle to custom path
uv run python demo_equity_research.py NVDA --json -o out/nvda_e2e.json

# Quick research mode (uses quick_llm for consensus/assumption/section deep-tier calls)
uv run python demo_equity_research.py NVDA --quick-research

# Skip verify steps
uv run python demo_equity_research.py NVDA --no-skip-verify

# Generate HTML trace visualization
uv run python demo_equity_research.py NVDA --visualize
```

**Run bundle outputs** (per ticker directory):

| File | Content |
|------|---------|
| `full_state.json` | Complete graph state snapshot |
| `progress_events.json` | Versioned `ProgressEvent` bus output (SSE-ready) |
| `research_traces.json` | Per-node `deps.trace()` log from each subgraph |
| `run_summary.json` | High-level summary (stages seen, api_calls, errors, warnings) |
| `run_tree.json` | Checkpoint resume tree (`list_run_tree` from SQLite) |

Use [`scripts/visualize_equity_research_trace.py`](tradingagents/scripts/visualize_equity_research_trace.py) to render the full trace as HTML.

## Architecture

```
tradingagents/equity_research/
├── graph/              # Outer LangGraph (setup.py, routers.py, checkpointer, human_review, nested)
├── agents/
│   ├── research_loop.py      # Inner R&D loop runtime (thesis graph)
│   ├── task_analysis.py      # Init spine: static consensus subgraph + gaps + graph bootstrap
│   ├── consensus/            # Thin wrapper → GenericResearchSubgraph + parent state mapping
│   ├── dynamic_planning.py
│   ├── modeling_workflow.py
│   ├── valuation_workflow.py
│   ├── branch_merge.py       # Thesis branch consolidation → thesis_ledger + core thesis Claim
│   ├── risk_mapping.py       # Risk→thesis mapping + catalyst calendar
│   ├── final_qa.py
│   ├── lead_analyst.py       # Domain agent orchestrator (not Task Decomposer)
│   └── domain/               # 9 domain analyst agents (logical roles)
├── runtime/            # GenericResearchSubgraph + SectionResearchSubgraph (PER loop, zero business logic)
│   ├── nodes/                  # skill_selector, planner, executor, section_executor, synthesizer, reflector, finalizer, human_review
│   └── utils/                  # context_compact, dedupe, step_payload, structured_invoke, search_memory, messages, domain_denylist, prompt_helpers, llm_invoke, llm_resolve, reflector_routing
├── tasks/              # TaskProfile configs (consensus, assumption, section_planner, section_research)
├── skills/             # SkillRegistry + implementations
├── tools/              # ToolRegistry, tool_router/set/grouping, skill_tools, system_tools, evidence_memory, memory_tools, stub_impl
├── state/
│   ├── equity_research_state.py
│   ├── research_graph.py     # Thesis exploration DAG
│   ├── ledgers.py
│   ├── schemas.py
│   └── blackboard.py         # BlackboardEntry schema for section-level cross-question sharing
├── memory/             # Collaborative memory retrieval + pruning + snapshots + conflict detection
├── evaluation/         # Aggregated thesis / IC scoring
├── prompts/            # rd_agent.py prompt pack
├── storage/            # PostgreSQL + in-memory fallback (pgvector, blackboard_store)
├── integrations/       # Perplexity, EDGAR, FMP, embeddings, Redis, sec_cache
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

### Branch Merge

After `valuation_workflow` completes, `branch_merge` selects top-4 thesis nodes by score (skipping rejected ones), merges them via LLM (`thesis_merge_prompt`), and writes consolidated results to `thesis_ledger` + creates a core `RECOMMENDATION` claim. See [equity_research/branch-merge.md](equity_research/branch-merge.md).

### Risk Mapping

`risk_mapping` maps discovered risks back to thesis nodes and builds a catalyst calendar. It uses either the `risk_counterthesis` skill (via `SkillRegistry`) or a fallback from `expectation_gaps`. See [equity_research/risk-mapping.md](equity_research/risk-mapping.md).

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

### Section Research Subgraph (`SectionResearchSubgraph`)

Distinct from `GenericResearchSubgraph`, this is the PER loop variant used inside `research_loop` for individual section research. Key differences:

| Feature | GenericResearchSubgraph | SectionResearchSubgraph |
|---------|------------------------|-------------------------|
| Planner | Query queue generation (Perplexity-based) | Multi-step todo plan (BFS/blackboard todos) |
| Executor | Batch Perplexity search | ReAct-style multi-step executor with tool routing |
| Reflector | Coverage score per dimension | Task completion + blackboard evidence extraction |
| Tool grouping | N/A | Three groups (retrieval, computation, action) with `ToolRouter` |
| Blackboard | N/A | Cross-question shared notes via `BlackboardEntry` schema |
| Parameter registry | N/A | `ParameterPreservingReducer` extracts + version-chains structured parameters |

The `SectionResearchSubgraph` replaces the generic node with specialized versions:
- `section_executor.py` — ReAct dispatch, step payload JSON for verify/compare/calculate actions
- `section_reflector.py` — Task-level reflector with blackboard auto-write and todo materialization
- `section_planner.py` — Initial + loop planning for multi-step todo research plans
- `tool_router.py` — Classifies executor tools into retrieval/computation/action groups before ToolNode

See [equity_research/section-research-subgraph.md](equity_research/section-research-subgraph.md) for full details.

### Parameter Preserving Reducer

Located in `runtime/parameter_*.py`, this three-phase pipeline (Map → Reduce → Compile) addresses parameter drift across section research iterations:

1. **Map**: LLM extracts structured parameters from evidence (key, value, unit, as_of date, confidence)
2. **Reduce**: Merges into `ParameterRegistry` with semantic key matching (Jaccard threshold 0.85), conflict detection (5% numeric tolerance), and append-only version chains
3. **Compile**: Renders a parameter grid text injected into synthesizer/reflector prompts

This prevents loss of critical financial figures during context compaction. See [equity_research/parameter-preserving-reducer.md](equity_research/parameter-preserving-reducer.md).

### Session Blackboard

A single-session cross-question note board for section research. Each PER iteration can extract findings, hypotheses, contradictions, and cross-question hints into `BlackboardEntry` objects. Entries are automatically extracted by the synthesizer (from evidence) and reflector (from coverage gaps). The board content is formatted and injected into planner/executor/reflector prompts within each session. After session end, entries are persisted to `BlackboardStore` (PostgreSQL or in-memory) with an LLM-generated summary for subsequent section sessions. See [equity_research/memory.md §5](equity_research/memory.md).

### SEC Table Chunking v2

SEC filing ingestion uses an improved chunker (`SecTableChunker` + `ParagraphChunker`) that detects fixed-width financial tables, splits them at row level (12 rows/chunk with 2-row overlap), tracks hierarchical parent labels, and reduces default paragraph chunk size from 800 to 300 words. This improves retrieval granularity and hit count significantly. TOC detection and line-anchor regex prevent false section switches. See [equity_research/sec-table-chunking.md](equity_research/sec-table-chunking.md).

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
| [equity_research/memory.md](equity_research/memory.md) | Ledger 分层、读写路径、检索评分公式（含 HitRate@10 82–88%）、证据追溯链 (~90%)；BranchMerge/RiskMapping |
| [equity_research/section-research-subgraph.md](equity_research/section-research-subgraph.md) | SectionResearchSubgraph: multi-step todo PER loop, ReAct executor, tool_router, blackboard integration |
| [equity_research/context.md](equity_research/context.md) | Context assembly: item caps + unified 32k budget + at most one soft compact; −23% context volume reduction; executor dialogue slim-down |
| [equity_research/skills-and-tools.md](equity_research/skills-and-tools.md) | Skill/Tool 注册、可见性、绑定与发现工具 |
| [equity_research/storage.md](equity_research/storage.md) | Redis、PostgreSQL、本地文件的配置与数据流 |
| [equity_research/sec-filing-rag.md](equity_research/sec-filing-rag.md) | SEC Filing RAG：MVP1 现状与规划模块 |
| [equity_research/sec-table-chunking.md](equity_research/sec-table-chunking.md) | SEC 表格感知分块 v2：行级拆分、层级标签、上下文段落 |
| [equity_research/parameter-preserving-reducer.md](equity_research/parameter-preserving-reducer.md) | ParameterPreservingReducer：三阶段参数提取与版本链架构 |
| [equity_research/branch-merge.md](equity_research/branch-merge.md) | BranchMerge: 论点分支整合算法，top-N 筛选 → LLM merge → ledger 写入 |
| [equity_research/risk-mapping.md](equity_research/risk-mapping.md) | RiskMapping: 风险到论点的映射 + 催化剂日历，skill-driven 回退路径 |

| 文档 | 英文说明 |
|------|----------|
| `file-structure.md` | Complete directory tree, execution flow, and API entry quick-reference |
| `agent-loop-and-tasks.md` | GenericResearchSubgraph PER loop, TaskProfile injection, current vs planned Task assignment |
| `memory.md` | Ledger layers, read/write paths, retrieval scoring formulas, **HitRate@10 82–88%**, **~90% evidence traceability** |
| `section-research-subgraph.md` | SectionResearchSubgraph: multi-step todo PER loop, ReAct executor, tool grouping, blackboard |
| `context.md` | Category A/B/C context strategy, unified 32k char budget, **−23% context volume reduction**; soft compact once-per-call limit |
| `skills-and-tools.md` | Skill/Tool registration, agent visibility filtering, binding & discovery tools |
| `storage.md` | Redis rate-limit/budget/cache, PostgreSQL stores, local file workspace config |
| `sec-filing-rag.md` | SEC filing ingestion pipeline (prefetch → RAG service → BM25+pgvector hybrid search) |
| `sec-table-chunking.md` | Table-aware chunking v2: row-level split, hierarchical label tracking, context paragraphs |
| `parameter-preserving-reducer.md` | Three-phase (Map→Reduce→Compile) parameter preservation with version chains |
| `branch-merge.md` | BranchMerge: thesis branch consolidation, scoring, ledger output |
| `risk-mapping.md` | RiskMapping: risk-to-thesis mapping, catalyst calendar generation |

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

For **LangSmith-based evaluation** (end-to-end, trajectory, faithfulness), see [README.md § Evaluation](../README.md#evaluation).

Key test files:

### Capability matrix

| Layer | Component | Role |
|-------|-----------|------|
| Subgraph runtime | `GenericResearchSubgraph` | PER loop executor |
| Skills registry | `skills/` | Methodology decoupling, ~85% skill-objective match rate in local tests |
| Code execution | E2B sandbox | Isolated Python environment for valuation computation, 95% result reproducibility |
| Task profile | `tasks/*.py` | Configuration injection (dimensions, prompts, schemas) |


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

---

See [README.md](../README.md) for the complete Equity Research technical guide (architecture through `dynamic_planning`, memory current vs roadmap, trace, compliance, and documentation index).

中文版：[README.zh-CN.md](../README.zh-CN.md) · [docs/zh/EQUITY_RESEARCH.md](zh/EQUITY_RESEARCH.md) · [文档索引](zh/README.md)
