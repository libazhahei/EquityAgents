# 股票研发智能体（Equity R&D-Agent）

> 英文版 | [EQUITY_RESEARCH.md](../EQUITY_RESEARCH.md)
>
> **完整技术文档：** [README.zh-CN.md](../../README.zh-CN.md)（中文）· [README.md](../../README.md)（英文）  
> **交易框架：** [TRADINGAGENTS.md](TRADINGAGENTS.md) · [英文版](../TRADINGAGENTS.md)

> 与主 TradingAgents 交易工作流并行的可选功能。  
> 由早期的 Hybrid Equity Research 主干演进为 R&D-Agent 研究范式。

## 概览

`EquityResearchGraph` 实现了一个**股票研发智能体（Equity R&D-Agent）**：

```text
Research Phase   →  thesis graph exploration, evidence, Quick Diligence
Development Phase →  modeling, valuation, section artifacts
Evaluation Phase  →  aggregated scoring, IC review, Final QA
```

**产品原则：** 不要让智能体一次性生成整份报告。先研究投资论点，再发展证据与模型，最后撰写各章节。

### 外层工作流（15 个 LangGraph 阶段节点）

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

### 内层研究循环（每次迭代）

在 `research_loop` 节点内执行（`agents/research_loop.py`）：

| 步骤 | 动作 |
|------|------|
| ① | 动态规划 — 阶段与预算分配 |
| ② | 从 `research_graph` 选择父论点节点 |
| ③ | 从 ledger 构建协作记忆上下文 |
| ④ | 识别关键研究问题 |
| ⑤ | 生成科学投资假设（五维评分） |
| ⑥ | 虚拟 IC — 选择有前景的分支 |
| ⑦ | 快速尽调 — 最多约 5 条证据；reject / park / full_diligence |
| ⑧ | 完整开发 — evidence retrieve → facts → verify → domain skills |
| ⑨ | 聚合论点评估 → 更新 `research_graph` |

当 `research_graph.best_node_id` 分数 ≥ 阈值、达到最大迭代次数，或阶段为 `convergence` 时停止。

### 报告章节（10 节）

| 章节 | ID |
|------|-----|
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

投资摘要**最后撰写**（IC 审阅之后），但在最终报告中**最先展示**。

---

### 状态机工作流与人工评审门禁 {#human-review-gates}

流水线实现为**多步状态机** — 每个阶段在进入下一阶段前验证其输入，关键决策点暴露**人工评审中断节点**（`human_review_1` 在共识/假设后，`human_review_2` 在 planner 后）。触发时，这些中断会暂停执行（通过 LangGraph checkpoint），以便人工审查输出并打上补丁后恢复。

| 场景 | 触发的门禁 | 返工路径 |
|------|-----------|---------|
| 研究深度不足 | `human_review_2` → patch sections | 恢复 `planner`，重新进入 `section_research` |
| 发现异常假设 | `human_review_1` → 修正 `assumption_view` | 恢复下游阶段 |
| 估值结果不合理 | `human_review_1` → 更新 `assumption_map` | 沿流水线修订转发 |
| 报告质量低于阈值 | `human_review_2` → 调整计划 | 重新规划受影响的章节 |

**性能表现：** 在本地区段测试中，初始端到端研究链的每步耗时控制在 **80–120 秒**。人工介入的返工机制通过在结构化门禁点早期捕获问题（而非事后补救），将整体返工率从预估的 30%+ 降至 **18%**。

Checkpoint/resume 能力由 [`graph/checkpointer.py`](tradingagents/equity_research/graph/checkpointer.py) 提供：以 ticker 为单位的 SQLite 数据库存放于 `{data_cache_dir}/checkpoints/equity_research/<TICKER>.db`，按 `er_run_tree` 索引。恢复时自动应用任何 patches。

#### 性能指标汇总

| 指标 | 数值 | 机制 |
|------|------|------|
| 单步延迟（初始 E2E 链路） | **80–120 秒** | LangGraph checkpoints 下顺序阶段执行 |
| 整体返工率 | **18%** | 人工评审门禁（HR1/HR2）在写作前捕获问题 |
| 无效搜索路径减少 | **−32%** vs. 平面穷举搜索 | 分支剪枝通过 `quick_diligence` 裁决（`reject`/`park`） + 分阶段预算分配 |
| 每股研究平均 token 消耗 | **−36%** 缩减 | 同样的分支剪枝 + 记忆修剪（`prune_stale_evidence`、`merge_similar_evidence`） |
| 上下文注入体积减少 | **−23%** | 记忆维护（去重 + 过期清理） + soft context compact（见 [context.md](../equity_research/context.md)） |
| 证据 HitRate@10 | **82%–88%** | BM25 + pgvector + RRF 混合检索通过 `RAGService`（见 [memory.md §2.1](../equity_research/memory.md)） |
| 研报结论证据可追溯率 | **~90%** | Evidence→Claim ledger 链，`BlackboardEntry` 中的 `related_evidence_ids`；claim 支撑 thesis 声明 |
| Skill–目标匹配率 | **~85%** | `SkillRegistry.select_for_objective()` 回退 + catalog frontmatter 过滤（见 [skills-and-tools.md](../equity_research/skills-and-tools.md)） |
| 估值计算可复现性 | **95%** | E2B sandbox 隔离 Python 执行（见 `tools/lc/code.py`、`integrations/e2b_sandbox.py`） |

## 快速开始

### 1. 安装可选依赖

```bash
pip install "tradingagents[equity-research]"
```

### 2. 配置 PostgreSQL + pgvector + Redis

```bash
createdb tradingagents_equity
psql -d tradingagents_equity -f scripts/setup_pgvector.sql
```

环境变量：

| 变量 | 用途 |
|----------|---------|
| `TRADINGAGENTS_POSTGRES_URL` | PostgreSQL 连接字符串 |
| `TRADINGAGENTS_REDIS_URL` | Redis URL（限流 + 预算） |
| `PERPLEXITY_API_KEY` | Perplexity Search API |
| `SEC_EDGAR_USER_AGENT` | SEC EDGAR user agent（邮箱） |
| `FMP_API_KEY` | Financial Modeling Prep（仅财报电话会议，非行情） |
| `TRADINGAGENTS_LLM_PROVIDER` | LLM 提供商（与交易图共享） |

### 3. 通过 Python API 运行

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

### 4. 通过 CLI 运行 — `demo_equity_research.py`

端到端 CLI，运行完整流水线并写入 run bundle：

```bash
# 基本运行（写入 out/<TICKER>_equity_<timestamp>/full_state.json）
uv run python demo_equity_research.py NVDA --date 2025-07-10

# 使用人工评审覆盖补丁
uv run python demo_equity_research.py NVDA \
    --human-review-json examples/human_review_passthrough.json

# 导出 JSON 到 stdout + 保存到自定义路径
uv run python demo_equity_research.py NVDA --json -o out/nvda_e2e.json

# Quick research 模式（consensus/assumption/section deep-tier 调用使用 quick_llm）
uv run python demo_equity_research.py NVDA --quick-research

# 跳过 verify 步骤
uv run python demo_equity_research.py NVDA --no-skip-verify

# 生成 HTML trace 可视化
uv run python demo_equity_research.py NVDA --visualize
```

**Run bundle 输出**（每个 ticker 目录）：

| 文件 | 内容 |
|------|------|
| `full_state.json` | 完整图状态快照 |
| `progress_events.json` | 版本化 `ProgressEvent` bus 输出（SSE-ready） |
| `research_traces.json` | 每个子图的 per-node `deps.trace()` 日志 |
| `run_summary.json` | 高层摘要（stages seen, api_calls, errors, warnings） |
| `run_tree.json` | Checkpoint resume 树（SQLite 中的 `list_run_tree`） |

可使用 [`scripts/visualize_equity_research_trace.py`](tradingagents/scripts/visualize_equity_research_trace.py) 渲染完整 trace 为 HTML。

## 架构

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

### Ledger

| Ledger | 用途 |
|--------|---------|
| **Evidence** | 带来源摘录，可靠性 / 新鲜度 |
| **Claim** | 与支持 / 反驳证据关联的判断 |
| **Assumption** | 预测与估值假设，含共识桥接 |
| **Consensus** | 结构化市场共识条目 |
| **Broker View** | 卖方评级、目标价、摘要 |
| **Forecast / Valuation** | 每次建模迭代的版本历史 |
| **Issue** | 门禁拒绝、阻塞问题、解决跟踪 |
| **Research Graph** | 论点分支 DAG 节点，含分数与产物 |

`sync_ledgers_from_legacy()` 在旧状态字段与 ledger 结构之间提供双向同步。Skill/Tool 应优先使用 `write_to_ledger()` 作为主写入路径。

### BranchMerge（论点合并）

`valuation_workflow` 完成后，`branch_merge` 按分数选出 top-4 论点节点（跳过 rejected），通过 LLM（`thesis_merge_prompt`）合并它们，并将整合结果写入 `thesis_ledger` + 创建核心 `RECOMMENDATION` claim。详见 [equity_research/branch-merge.md](../equity_research/branch-merge.md)。

### RiskMapping（风险映射）

`risk_mapping` 将发现的風險映射回论点节点并构建催化剂日历。它使用 `risk_counterthesis` skill（通过 `SkillRegistry`）或从 `expectation_gaps` 回退。详见 [equity_research/risk-mapping.md](../equity_research/risk-mapping.md)。

### 领域智能体

`agents/domain/` 中的薄封装，由 `LeadAnalystAgent` 调度：

| 智能体 | Skills |
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

### Skills（注册表）

| Skill | 用途 |
|-------|---------|
| `dynamic_research_planning` | 阶段感知规划与预算分配 |
| `thesis_exploration_dag` | 初始化论点分支（revenue / margin / multiple / bear / FCF） |
| `scientific_investment_reasoning` | 结构化假设生成（委托给 research loop） |
| `collaborative_memory` | 跨分支 ledger 检索 |
| `broker_consensus_mining` | 卖方观点与共识 |
| `variant_view_discovery` | 预期差距 / variant view |
| `business_model_analysis` | 收入驱动与单位经济 |
| `industry_analysis` | 行业与竞争格局 |
| `historical_financial_analysis` | 历史财务趋势 |
| `forecast_assumption_builder` | 驱动变量 → 假设 ledger 条目 |
| `valuation` | 通过计算器确定性目标价 |
| `risk_counterthesis` | 风险与论点映射 |
| `catalyst_monitoring` | 催化剂日历 |
| `standardized_qa` | 证据 / 模型 / 合规评分 |
| `section_writing` | 基于已验证 claim 的章节草稿上下文 |

Prompt 模板位于 `prompts/rd_agent.py`（任务分析、规划、假设、快速尽调、论点合并等）。

### Section Research Subgraph (`SectionResearchSubgraph`)

与 `GenericResearchSubgraph` 不同，这是 `research_loop` 内部用于个股章节研究的 PER 循环变体。关键差异：

| 特性 | GenericResearchSubgraph | SectionResearchSubgraph |
|------|------------------------|-------------------------|
| Planner | Query queue 生成（Perplexity 驱动） | 多步 todo plan（BFS/blackboard todos） |
| Executor | Perplexity 批量搜索 | ReAct 式多步 executor + 工具路由 |
| Reflector | 各维度覆盖率评分 | 任务完成度 + blackboard 证据提取 |
| 工具分组 | N/A | 三组（retrieval/computation/action）with `ToolRouter` |
| Blackboard | N/A | 跨 question 共享笔记 via `BlackboardEntry` schema |
| 参数注册表 | N/A | `ParameterPreservingReducer` 提取 + 版本链结构化参数 |

`SectionResearchSubgraph` 用专用版本替换通用节点：
- `section_executor.py` — ReAct dispatch，verify/compare/calculate 的 step payload JSON
- `section_reflector.py` — 任务级 reflector，blackboard 自动写入 + todo 实例化
- `section_planner.py` — 初始 + 循环规划，用于多步 todo 研究计划
- `tool_router.py` — 在执行前将工具分类为 retrieval/computation/action 三组

详见 [equity_research/section-research-subgraph.md](../equity_research/section-research-subgraph.md)。

### Parameter Preserving Reducer（参数保留 Reducer）

位于 `runtime/parameter_*.py`，该三阶段管道（Map → Reduce → Compile）解决 section 研究迭代间的参数漂移问题：

1. **Map**：LLM 从证据中提取结构化参数（key, value, unit, as_of date, confidence）
2. **Reduce**：通过语义 key 匹配（Jaccard threshold 0.85）、冲突检测（5% 数值容差）、append-only 版本链合并到 `ParameterRegistry`
3. **Compile**：渲染参数网格文本注入 synthesizer/reflector prompts

此设计防止了关键财务数据在 context 压缩过程中丢失。详见 [equity_research/parameter-preserving-reducer.md](../equity_research/parameter-preserving-reducer.md)。

### Session Blackboard（会话黑板）

section research 的单 session 跨 question 笔记板。每次 PER 迭代可将发现、假设、矛盾和跨 question 线索提取为 `BlackboardEntry` 对象。条目由 synthesizer（来自证据）和 reflector（来自覆盖率缺口）自动提取。板内容在 session 内格式化并注入 planner/executor/reflector prompts。Session 结束后，条目持久化到 `BlackboardStore`（PostgreSQL 或内存），并附带 LLM 生成的摘要供后续 section sessions 使用。详见 [equity_research/memory.md §5](../equity_research/memory.md)。

### SEC Table Chunking v2

SEC 文件摄取使用改进的分块器（`SecTableChunker` + `ParagraphChunker`），检测固定宽度财务报表，按行级别拆分（每块 12 行 + 2 行重叠），追踪分层父标签，并将默认段落分块大小从 800 减少到 300 词。这显著提高了检索粒度和命中数。TOC 检测和行锚正则防止错误的章节切换。详见 [equity_research/sec-table-chunking.md](../equity_research/sec-table-chunking.md)。

### 评估

`evaluation/aggregators.py` 实现加权论点评分：

```text
evidence_strength (20%) + consensus_gap (20%) + financial_materiality (20%)
+ valuation_impact (15%) + catalyst_clarity (10%) + risk_adjusted (10%) + novelty (5%)
```

IC 审阅使用 `aggregate_ic_scores()`，并将阻塞问题记录到 `issue_ledger`。

### 系统架构专题

以下中文文档对模块内部机制做专项说明（文件结构、Memory、Context、Skills/Tools 控制方案）：

| 文档 | 内容 |
|------|------|
| [equity_research/file-structure.md](../equity_research/file-structure.md) | 完整目录树、执行流与代码入口速查 |
| [equity_research/agent-loop-and-tasks.md](../equity_research/agent-loop-and-tasks.md) | GenericResearchSubgraph PER 循环、TaskProfile、Task 分配现状与规划 |
| [equity_research/memory.md](../equity_research/memory.md) | Ledger 分层、读写路径、检索评分公式（含 HitRate@10 82–88%）、证据追溯链 (~90%） |
| [equity_research/section-research-subgraph.md](../equity_research/section-research-subgraph.md) | SectionResearchSubgraph: 多步 todo PER loop, ReAct executor, tool_router, blackboard |
| [equity_research/context.md](../equity_research/context.md) | Context 组装：条数策展 + 统一预算（默认 32000） + 至多一次 soft compact；−23% 上下文体积缩减；executor 对话瘦身 |
| [equity_research/skills-and-tools.md](../equity_research/skills-and-tools.md) | Skill/Tool 注册、可见性、绑定与发现工具 |
| [equity_research/storage.md](../equity_research/storage.md) | Redis、PostgreSQL、本地文件的配置与数据流 |
| [equity_research/sec-filing-rag.md](../equity_research/sec-filing-rag.md) | SEC Filing RAG：MVP1 现状与规划模块 |
| [equity_research/sec-table-chunking.md](../equity_research/sec-table-chunking.md) | SEC 表格感知分块 v2：行级拆分、层级标签、上下文段落 |
| [equity_research/parameter-preserving-reducer.md](../equity_research/parameter-preserving-reducer.md) | ParameterPreservingReducer：三阶段参数提取与版本链架构 |
| [equity_research/branch-merge.md](../equity_research/branch-merge.md) | BranchMerge: 论点分支整合算法，top-N 筛选 → LLM merge → ledger 写入 |
| [equity_research/risk-mapping.md](../equity_research/risk-mapping.md) | RiskMapping: 风险到论点的映射 + 催化剂日历，skill-driven 回退路径 |

## 设计约束

- 目标价与 EPS 来自**确定性计算器**，而非 LLM 编造
- `7_valuation` 要求 `requires_model_output: True`
- 评级基于 `12_month_total_return`（价格上涨空间 + 股息收益率）
- 无证据的 claim 不应达到 `verified` 状态
- IC / Final QA 可路由回 `dynamic_planning`、`modeling_workflow` 或 `valuation_workflow`
- FMP **仅用于**财报电话会议转录，不用于行情数据

## 测试

```bash
pytest tests/equity_research/ -m "not integration" -q
```

**基于 LangSmith 的评估**（端到端、轨迹、忠实度）见 [README.zh-CN.md § 评估](../../README.zh-CN.md#evaluation)。

关键测试文件：

| 文件 | 覆盖范围 |
|------|--------|
| `test_workflow_spine.py` | 外层图节点名称 |
| `test_research_loop.py` | 内层循环与图更新 |
| `test_research_graph.py` | 父节点选择、分支合并、评分 |
| `test_memory_retrieval.py` | 协作记忆采样 |
| `test_ledgers.py` | Ledger 同步与 `write_to_ledger` |
| `test_routers.py` | 条件路由 |
| `test_e2e_mini_report.py` | 完整图冒烟（mock LLM） |

## 内存回退

在配置中设置 `equity_research_use_memory=True` 可在无 PostgreSQL/Redis 时运行。

---

完整股票研究技术指南（架构至 `dynamic_planning`、记忆现状与路线图、追踪、合规及文档索引）见 [README.zh-CN.md](../../README.zh-CN.md)。
