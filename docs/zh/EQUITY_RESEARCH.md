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

## 架构

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
| [equity_research/memory.md](../equity_research/memory.md) | Ledger 分层、读写路径、检索评分与导出 |
| [equity_research/context.md](../equity_research/context.md) | Context 组装：条数策展 + 统一预算（默认 32000）+ 至多一次 soft compact；executor 对话瘦身 |
| [equity_research/skills-and-tools.md](../equity_research/skills-and-tools.md) | Skill/Tool 注册、可见性、绑定与发现工具 |
| [equity_research/storage.md](../equity_research/storage.md) | Redis、PostgreSQL、本地文件的配置与数据流 |
| [equity_research/sec-filing-rag.md](../equity_research/sec-filing-rag.md) | SEC Filing RAG：MVP1 现状与规划模块 |

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
