# 中文文档索引

> 本页汇总 TradingAgents 与股票研究（Equity Research）相关的中文文档，便于按角色与阅读顺序导航。

---

## 推荐阅读顺序

| 顺序 | 文档 | 说明 |
|------|------|------|
| 1 | [README.zh-CN.md](../../README.zh-CN.md) | **主文档**：股票研究完整技术指南（安装、架构、共识与假设、研究循环、记忆、追踪、合规、评估） |
| 2 | [EQUITY_RESEARCH.md](EQUITY_RESEARCH.md) | 股票研发智能体产品概览：外层/内层工作流、章节结构、快速开始 |
| 3 | [equity_research/file-structure.md](../equity_research/file-structure.md) | 模块目录树与代码入口速查 |
| 4 | [equity_research/agent-loop-and-tasks.md](../equity_research/agent-loop-and-tasks.md) | GenericResearchSubgraph PER 循环与 Task 分配 |
| 5 | [runtime/consensus.md](runtime/consensus.md) → [runtime/assumption.md](runtime/assumption.md) → [runtime/section_planner.md](runtime/section_planner.md) | 初始化阶段三个子图的运行时说明 |
| 6 | [equity_research/memory.md](../equity_research/memory.md) · [context.md](../equity_research/context.md) · [skills-and-tools.md](../equity_research/skills-and-tools.md) · [storage.md](../equity_research/storage.md) · [sec-filing-rag.md](../equity_research/sec-filing-rag.md) | 横切机制：记忆、上下文、技能/工具、存储、SEC RAG |
| 7 | [ARCHITECTURE.md](../ARCHITECTURE.md) | 全项目架构设计（含交易图与数据流） |
| 8 | [TRADINGAGENTS.md](TRADINGAGENTS.md) | 上游多智能体**交易框架**文档（与股票研究并行，非主路径） |

---

## 按角色查阅

| 角色 | 建议阅读 |
|------|----------|
| **产品 / 研究负责人** | [README.zh-CN.md](../../README.zh-CN.md) 概览 → [EQUITY_RESEARCH.md](EQUITY_RESEARCH.md) 工作流与章节 |
| **后端 / 智能体开发** | [file-structure.md](../equity_research/file-structure.md) → [agent-loop-and-tasks.md](../equity_research/agent-loop-and-tasks.md) → [runtime/](runtime/) 子图运行时 |
| **Prompt / Skill 作者** | [skills-and-tools.md](../equity_research/skills-and-tools.md) · [context.md](../equity_research/context.md) · 各 runtime 文档中的 Prompt 章节 |
| **数据 / 基础设施** | [storage.md](../equity_research/storage.md) · [memory.md](../equity_research/memory.md) |
| **交易框架用户** | [TRADINGAGENTS.md](TRADINGAGENTS.md) · [ARCHITECTURE.md](../ARCHITECTURE.md) |
| **测试 / 评估** | [README.zh-CN.md § 评估](../../README.zh-CN.md#evaluation) · [EQUITY_RESEARCH.md § 测试](EQUITY_RESEARCH.md#测试) |

---

## 文档清单

### 主文档

| 文档 | 说明 |
|------|------|
| [README.zh-CN.md](../../README.zh-CN.md) | 股票研究主技术文档（中文） |
| [README.md](../../README.md) | 同上（英文） |

### 中文翻译（`docs/zh/`）

| 文档 | 说明 |
|------|------|
| [TRADINGAGENTS.md](TRADINGAGENTS.md) | 多智能体 LLM 金融交易框架（上游 TradingAgents） |
| [EQUITY_RESEARCH.md](EQUITY_RESEARCH.md) | 股票研发智能体产品概览与工作流 |
| [runtime/section_planner.md](runtime/section_planner.md) | Section Planner 子图：章节问题树编译 |
| [runtime/consensus.md](runtime/consensus.md) | Consensus 子图：市场共识五维结构化视图 |
| [runtime/assumption.md](runtime/assumption.md) | Assumption 子图：共识背后隐含假设探测 |

### 系统架构专题（`docs/equity_research/`，已为中文）

| 文档 | 说明 |
|------|------|
| [file-structure.md](../equity_research/file-structure.md) | Equity Research 完整目录树、执行流与 API 入口 |
| [agent-loop-and-tasks.md](../equity_research/agent-loop-and-tasks.md) | 三层 Agent 架构、PER 循环、TaskProfile 与 Task 分配 |
| [memory.md](../equity_research/memory.md) | Ledger 分层、读写路径、检索评分与导出 |
| [context.md](../equity_research/context.md) | Context 组装：条数策展 + 统一预算（默认 32000）+ 至多一次 soft compact；executor 对话瘦身 |
| [skills-and-tools.md](../equity_research/skills-and-tools.md) | Skill/Tool 注册、可见性白名单、绑定与发现 |
| [storage.md](../equity_research/storage.md) | PostgreSQL、Redis、本地文件的配置与数据流 |
| [sec-filing-rag.md](../equity_research/sec-filing-rag.md) | SEC 申报 RAG：MVP1 现状与规划模块 |
| [sec-table-chunking.md](../equity_research/sec-table-chunking.md) | SEC 表格感知分块 v2：行级拆分、层级标签、上下文段落 |

### 全项目架构

| 文档 | 说明 |
|------|------|
| [ARCHITECTURE.md](../ARCHITECTURE.md) | TradingAgents 项目架构设计（交易图、数据流、CLI、配置） |

### 英文对照

| 中文 | 英文 |
|------|------|
| [TRADINGAGENTS.md](TRADINGAGENTS.md) | [docs/TRADINGAGENTS.md](../TRADINGAGENTS.md) |
| [EQUITY_RESEARCH.md](EQUITY_RESEARCH.md) | [docs/EQUITY_RESEARCH.md](../EQUITY_RESEARCH.md) |
| [runtime/*.md](runtime/) | `tradingagents/equity_research/agents/*/RUNTIME.md` |

---

## 语言切换

- **股票研究主文档**： [README.zh-CN.md](../../README.zh-CN.md) | [README.md](../../README.md)
- **交易框架**： [TRADINGAGENTS.md](TRADINGAGENTS.md) | [TRADINGAGENTS.md（英文）](../TRADINGAGENTS.md)
- **产品概览**： [EQUITY_RESEARCH.md](EQUITY_RESEARCH.md) | [EQUITY_RESEARCH.md（英文）](../EQUITY_RESEARCH.md)
