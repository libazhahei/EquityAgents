完成。下面是合并后的完整设计文档 v2.1，包含所有 Redis 角色和 Markdown Memory 补充。你可以直接保存为项目根目录的 `ARCHITECTURE.md`。

---

# Agentic Equity Research R&D System

## 技术设计文档 v2.1

> 版本：v2.1 | 最后更新：2026-06-22 | 作者：System Architect (Agent)
> 状态：Design Complete, Ready for Phase 0 Implementation

---

## 目录

1. [系统定位与设计哲学](#1-系统定位与设计哲学)
2. [总体架构](#2-总体架构)
3. [Agent 角色与职责](#3-agent-角色与职责)
4. [R&D 闭环设计](#4-rd-闭环设计)
5. [假设 DAG 与多路径探索公式](#5-假设-dag-与多路径探索公式)
6. [Memory 架构：四层存储模型](#6-memory-架构四层存储模型)
7. [跨分支协同记忆与冲突仲裁](#7-跨分支协同记忆与冲突仲裁)
8. [RAG 四种检索场景](#8-rag-四种检索场景)
9. [券商研报结构约束](#9-券商研报结构约束)
10. [LangGraph 状态与流程设计](#10-langgraph-状态与流程设计)
11. [开发阶段：财务模型与估值](#11-开发阶段财务模型与估值)
12. [Perplexity API 集成](#12-perplexity-api-集成)
13. [Redis 角色](#13-redis-角色)
14. [评估体系](#14-评估体系)
15. [MVP 定义与实施路线](#15-mvp-定义与实施路线)

---

## 1. 系统定位与设计哲学

### 1.1 系统定位

> **Agentic Equity Research R&D System** 是一个以投资假设为驱动核心、以公开数据为证据基础、以财务模型和估值为验证手段、以券商研报结构为输出约束的多智能体研究系统。

与普通 Deep Research 的关键区别：

| 维度 | 普通 Deep Research | 本系统 |
|---|---|---|
| 驱动核心 | 用户问题 | 预期差假设 |
| 搜索方式 | 开放探索 | 假设锚定搜索 |
| 输出形式 | 信息总结 | 可审计投资论证 |
| 验证机制 | 无 | Evidence + Computation + Valuation |
| 质量保证 | LLM 自评 | 多层 Reviewer + 确定性检查 |
| 核心价值 | 信息压缩 | Alpha 发现 + 可复现逻辑 |

### 1.2 核心设计原则

```
原则 1: 报告由 verified claims 生成，不由 search summaries 生成。
原则 2: 每个 hypothesis 必须有验证条件和停止条件。
原则 3: 每个 claim 必须绑定 evidence 或 computation。
原则 4: 每个 computation 必须可复现（代码 + 数据版本）。
原则 5: 每个 chart 必须追溯到底层数据。
原则 6: 每个 section 必须经过 reviewer。
原则 7: LLM 负责研究推理，不负责最终事实裁决。
原则 8: 必须主动搜索反证，保持 balanced view。
原则 9: RAG 是检索能力，不是裁决者，不是硬规则引擎。
原则 10: Report Template 是硬约束，不是建议。
```

---

## 2. 总体架构

### 2.1 系统分层

```
┌────────────────────────────────────────────────────────┐
│  0. Report Mandate & Structure Controller              │
│     输入 ticker / report type / horizon / style         │
│     加载券商八段研报模板和 section 约束                  │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  1. Consensus & Expectation Gap Discovery              │
│     市场共识提取 / 股价隐含预期 / 潜在 Alpha 识别        │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  2. RESEARCH PHASE                                     │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 2.1 Dynamic Planning (Research Budget)            │  │
│  │ 2.2 Hypothesis DAG (自适应多分支探索)              │  │
│  │ 2.3 Scientific Reasoning Pipeline (推理管道)       │  │
│  │ 2.4 Virtual Evaluation (假设预筛选)                │  │
│  │ 2.5 Collaborative Memory (跨分支协同)              │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  3. DEVELOPMENT PHASE                                  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ 3.1 Evidence Retrieval & Acquisition              │  │
│  │ 3.2 Filing / Transcript Extraction                │  │
│  │ 3.3 Industry & Peer Data Collection               │  │
│  │ 3.4 Business Driver Decomposition                  │  │
│  │ 3.5 Financial Model Development (Progressive)      │  │
│  │ 3.6 Valuation Model Development                    │  │
│  │ 3.7 Chart / Table Generation                       │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  4. CLAIM & THESIS VERIFICATION                        │
│     Claim-Evidence binding / 反证检查 / 计算验证       │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  5. SECTION WRITING                                    │
│     按八段结构写 section / citation 自动嵌入            │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  6. AGGREGATED EVALUATION (Investment Committee)       │
│     统一审查 thesis / model / valuation / risk         │
└────────────────────────────────────────────────────────┘
                          │
┌────────────────────────────────────────────────────────┐
│  7. FINAL REPORT ASSEMBLY                              │
│     首页摘要 / 正文 / 图表 / 财务附录 / 风险提示        │
└────────────────────────────────────────────────────────┘
```

### 2.2 三层循环结构

```
外层: Section Loop
  按八段结构逐一完成，section_coverage 追踪完成度
        │
  中层: Hypothesis R&D Loop
    提出假设 → 虚拟评估 → 证据开发 → 计算开发 → claim 验证 → section draft
        │
  内层: Development Debug Loop
    生成计算任务 → 小数据原型验证 → 全量计算 → 存储结果
```

---

## 3. Agent 角色与职责

### 3.1 Agent 清单

| # | Agent | 阶段 | 职责 | 输入 | 输出 |
|---|---|---|---|---|---|
| 1 | Report Mandate Agent | Init | 确定 ticker、报告类型、时间范围、风格 | 用户指令 | ReportMandate |
| 2 | Template Controller | Init | 加载八段模板和每段 required_outputs | ReportMandate | SectionConstraints |
| 3 | Consensus Agent | Research | 提取市场共识、一致预期、股价隐含预期 | ticker, price, estimates | ConsensusView |
| 4 | Expectation Gap Agent | Research | 识别预期差和潜在 Alpha 来源 | ConsensusView, filings | ExpectationGaps |
| 5 | Hypothesis Generator | Research | 生成可验证投资假设 | ExpectationGaps, template | HypothesisDAG |
| 6 | Virtual Evaluation Agent | Research | 对假设做多维评分和剪枝 | HypothesisDAG | RankedHypotheses |
| 7 | Research Planner | Research | 动态分配搜索/阅读/计算预算 | phase, hypotheses | ResearchBudget |
| 8 | Evidence Retrieval Agent | Development | 执行假设锚定搜索，获取公开资料 | hypothesis, budget | Documents, EvidenceFragments |
| 9 | Extraction Agent | Development | 从非结构化文档抽取 KPI、guidance、facts | EvidenceFragments | StructuredFacts |
| 10 | Business Driver Agent | Development | 拆解收入/利润驱动到最小单元 | StructuredFacts, filings | BusinessDrivers |
| 11 | Financial Forecast Agent | Development | 构建三年盈利预测 | BusinessDrivers, facts | ForecastModel |
| 12 | Valuation Agent | Development | 选择估值法，计算目标价 | ForecastModel, peer data | ValuationModel |
| 13 | Chart Agent | Development | 生成 matplotlib/plotly 图表 | computation results | Charts |
| 14 | Claim Verification Agent | Verification | 验证 claim 的证据和计算支撑 | claims, evidence, computation | VerifiedClaims |
| 15 | Section Writer Agent | Writing | 按模板写 section，嵌入 citation | verified claims, template | SectionDraft |
| 16 | Section Reviewer Agent | Review | 检查 section 完整性、一致性 | SectionDraft | ReviewFeedback |
| 17 | Investment Committee Agent | Final | 统一审查 thesis/valuation/risk | 全报告 | FinalReview, Rating |
| 18 | Report Assembler | Final | 生成完整报告文档 | all section drafts | FinalReport |

### 3.2 Agent 禁止行为

| Agent | 禁止 |
|---|---|
| Hypothesis Generator | 不提出无法公开验证的假设 |
| Evidence Retrieval Agent | 不直接写入报告文本 |
| Extraction Agent | 不凭空补全缺失数据 |
| Financial Forecast Agent | 不跳过 business driver 直接猜数字 |
| Valuation Agent | 不在不说明理由的情况下选择估值法 |
| Claim Verification Agent | 不接受无 source 的 claim |
| Section Writer Agent | 不添加未被验证的新 claim |
| 所有 Agent | 不绕过 Safety Shield / Reviewer 直接写入 final report |

### 3.3 Main Agent + Skills 模式

每个 LangGraph node 由一个 main agent 负责。Agent 内部根据 task 类型动态选择可插拔的 skill：

```python
# 每个 Skill 有明确的 Manifest:
class SkillManifest:
    skill_name: str
    description: str
    inputs: dict[str, type]
    outputs: dict[str, type]
    tools_required: list[str]
    evaluation_criteria: list[str]

# Agent 运行时:
def main_agent(state, task):
    skill = get_skill_for_task(task.skill_name)
    inputs = prepare_inputs(state, skill.inputs)
    result = skill.execute(inputs)
    return update_state(state, result)
```

---

## 4. R&D 闭环设计

### 4.1 R&D 循环语义映射

| R&D-Agent 原模块 | Equity Research 映射 | 说明 |
|---|---|---|
| Dynamic Planning | Research Budget Planner | 搜索/阅读/计算预算的动态分配 |
| Adaptive DAG Exploration | Investment Hypothesis DAG | 多分支假设探索与剪枝 |
| Scientific Reasoning Pipeline | Analyst Reasoning Pipeline | 共识识别 → 关键变量 → 预期差假设 |
| Virtual Evaluation | Hypothesis Scoring | 考虑 materiality + model linkage |
| Collaborative Memory | Cross-Branch Discovery Pool | 跨分支证据和发现共享 |
| Efficient Coding Workflow | Progressive Financial Modeling | 原型模型 → 完整三表/估值 |
| Aggregated Evaluation | Investment Committee Review | 统一审查 thesis + model + valuation |

### 4.2 Research Phase 详细流程

```
输入: SectionConstraints + ExpectationGaps
        │
        ▼
┌──────────────────────────────┐
│ 4.2.1 Research Budget Planner│
│ 根据 phase 分配预算:           │
│ - early: 广度优先，禁止 DCF    │
│ - mid: 深度验证，允许 extraction │
│ - late: 模型收敛，允许完整估值  │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.2.2 Hypothesis DAG Builder │
│ 生成多分支假设图:              │
│ Root → 4-6 主假设              │
│ 每个主假设 → 2-4 子假设        │
│ 记录状态和评分                 │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.2.3 Scientific Reasoning   │
│ 对每个假设执行:                │
│ 市场共识是什么？               │
│ 关键变量是什么？               │
│ 预期差在哪里？                 │
│ 需要什么证据？                 │
│ 影响哪些财务指标？             │
│ 影响哪种估值方法？             │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.2.4 Virtual Evaluation     │
│ 多维评分 → 排序 → 剪枝         │
│ 只保留 Top-N 进入 Development  │
└──────────────────────────────┘
```

### 4.3 Development Phase 详细流程

```
输入: RankedHypotheses + ResearchBudget
        │
        ▼
┌──────────────────────────────┐
│ 4.3.1 Evidence Retrieval     │
│ Perplexity + 官方源搜索        │
│ 结果存 Document Registry      │
│ 相关段落存 Evidence Fragment  │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.3.2 Fact Extraction        │
│ 从 Evidence Fragment 抽取:    │
│ - KPI 数值                    │
│ - management guidance         │
│ - segment data                │
│ - competitive info            │
│ 存入 Structured Fact Store    │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.3.3 Business Driver Decomp │
│ 拆解收入/利润驱动:             │
│ Revenue = Σ(volume × ASP)    │
│ Gross Profit = Revenue × GM  │
│ 每个 driver 绑定 data source  │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.3.4 Financial Model Dev    │
│ Progressive:                  │
│ Prototype: rough EPS/PE      │
│ Full Model: 3-year forecast  │
│ 所有 assumption 绑定 source   │
└──────────────────────────────┘
        │
        ▼
┌──────────────────────────────┐
│ 4.3.5 Valuation Model Dev    │
│ 选择估值方法 → 计算目标价      │
│ → peer comparison            │
│ → sensitivity table          │
└──────────────────────────────┘
```

---

## 5. 假设 DAG 与多路径探索公式

### 5.1 假设状态机

```
proposed ──→ accepted ──→ in_research ──→ verified
    │              │              │
    └──────────────┴──────────────┴──→ rejected
                                       │
                                  partially_supported ──→ needs_more_research
```

### 5.2 假设评分公式（Virtual Evaluation）

```python
def compute_hypothesis_score(h):
    """
    在投入搜索/计算资源之前，用 LLM 对假设做虚拟评估。
    权重由 sell-side research 特性定义。
    """
    scores = {
        "materiality":         score_materiality(h),         # 权重 0.20
        "variant_perception":  score_variant(h),             # 权重 0.20
        "model_linkage":       score_model_linkage(h),       # 权重 0.20
        "verifiability":       score_verifiability(h),       # 权重 0.15
        "evidence_availability": score_evidence_avail(h),    # 权重 0.10
        "novelty":             score_novelty(h),             # 权重 0.10
        "research_cost":       estimate_research_cost(h),    # 扣分项 权重 0.05
    }

    priority = (
        0.20 * scores["materiality"]
        + 0.20 * scores["variant_perception"]
        + 0.20 * scores["model_linkage"]
        + 0.15 * scores["verifiability"]
        + 0.10 * scores["evidence_availability"]
        + 0.10 * scores["novelty"]
        - 0.05 * scores["research_cost"]
    )
    return priority
```

### 5.3 剪枝条件

```
剪枝 (status → rejected):
├── materiality < 0.3
├── model_linkage < 0.2（对财务模型几乎无影响）
├── verifiability < 0.3（无法用公开数据验证）
├── 与最新 10-K/10-Q 强冲突
└── 只支持常识性描述，无 alpha

保留在顶层:
├── materiality ≥ 0.6
├── variant_perception ≥ 0.5
└── model_linkage ≥ 0.5
```

### 5.4 动态研究预算分配

```python
def allocate_budget(phase, hypothesis_scores, time_remaining_pct):
    if phase == "early":
        return Budget(
            max_search_queries=10,
            max_documents=15,
            max_tokens_per_doc=3000,
            max_deep_extraction_docs=3,
            allow_full_dcf=False,
            allow_full_peer_comp=False,
        )
    elif phase == "mid":
        top_n = sum(1 for s in hypothesis_scores if s > 0.7)
        return Budget(
            max_search_queries=8 + top_n * 3,
            max_documents=20,
            max_tokens_per_doc=5000,
            max_deep_extraction_docs=5,
            allow_full_dcf=False,
            allow_full_peer_comp=True,
        )
    else:  # late
        return Budget(
            max_search_queries=5,
            max_documents=10,
            max_tokens_per_doc=8000,
            max_deep_extraction_docs=8,
            allow_full_dcf=True,
            allow_full_peer_comp=True,
        )
```

### 5.5 假设停止条件

```python
def evaluate_hypothesis_stop(h):
    can_accept = (
        len(h.supporting_evidence_ids) >= 2
        and all(e.source_reliability in ("high", "medium") for e in h.supporting_evidence)
        and len(h.contradicting_evidence_ids) == 0
        and h.computation_results is not None
        and h.computation_results.consistent_with_hypothesis
    )
    if can_accept:
        return ("verified", True)

    should_reject = (
        len(h.contradicting_evidence_ids) >= 1
        and any(e.source_reliability == "high" for e in h.contradicting_evidence)
        or (h.computation_results is not None and h.computation_results.strongly_contradicts)
    )
    if should_reject:
        return ("rejected", True)

    if h.research_iterations >= h.max_iterations:
        return ("needs_more_research", True)

    return ("continue", False)
```

---

## 6. Memory 架构：四层存储模型

### 6.1 总览

```
Layer 1 — Document Registry      SQL exact lookup     (元数据 + 指针)
Layer 2 — Evidence Fragment      pgvector + hybrid    (摘录 + embedding)
Layer 3 — Structured Fact        SQL exact lookup     (结构化 KPI + 数据)
Layer 4 — Research Trace         SQL + JSONB          (审计日志)

跨层增强:
  Cross-Branch Discovery Pool   pgvector              (协同记忆)
  Knowledge Library             pgvector              (跨公司持久化知识)
  
人类可读镜像:
  Markdown Memory Mirror        文件系统              (git 可追踪的研究笔记)
```

### 6.2 Layer 1: Document Registry

```sql
CREATE TABLE document_registry (
    doc_id              TEXT PRIMARY KEY,
    ticker              TEXT NOT NULL,
    source_type         TEXT NOT NULL,        -- '10-K','10-Q','earnings_call','press_release','news','industry_report'
    title               TEXT,
    published_date      DATE,
    fiscal_period       TEXT,                 -- 'FY2024','Q3FY2025'
    source_url          TEXT,
    retrieved_at        TIMESTAMP,
    file_hash           TEXT,
    access_path         TEXT,                 -- 本地路径或 API endpoint
    doc_fingerprint     TEXT UNIQUE,          -- title + date + ticker + source_type 的 hash
    processing_status   TEXT DEFAULT 'registered',
    created_at          TIMESTAMP DEFAULT NOW()
);
```

规则：
- 全文不存数据库，存文件系统或 API endpoint。
- `doc_fingerprint` 唯一约束，防止重复注册。
- 所有 agent 开始检索前先查此表。

### 6.3 Layer 2: Evidence Fragment

```sql
CREATE TABLE evidence_fragment (
    fragment_id         TEXT PRIMARY KEY,
    doc_id              TEXT REFERENCES document_registry(doc_id),
    ticker              TEXT NOT NULL,

    section_in_source   TEXT,
    page_number         INT,
    paragraph_index     INT,

    excerpt_text        TEXT NOT NULL,
    excerpt_context     TEXT,

    extracted_by_task_id TEXT,
    extraction_confidence FLOAT,

    fragment_type       TEXT,                 -- 'revenue','margin','guidance','risk','competitor','industry','legal','strategy'
    source_reliability  TEXT CHECK (source_reliability IN ('high','medium','lower')),

    cross_branch_shareable BOOLEAN DEFAULT FALSE,
    embedding           VECTOR(768),

    created_at          TIMESTAMP DEFAULT NOW()
);
```

存储规则：
- 只存被至少一个 task 标记为 relevant 的段落。
- 全文档不存 embedding。
- `fragment_type` 枚举严格控制。

### 6.4 Layer 3: Structured Fact

```sql
CREATE TABLE structured_fact (
    fact_id             TEXT PRIMARY KEY,
    ticker              TEXT NOT NULL,
    fact_type           TEXT NOT NULL,        -- 'revenue','segment_revenue','gross_margin','eps','capex','fcf','market_share','guidance'
    metric_name         TEXT NOT NULL,
    numeric_value       DOUBLE PRECISION,
    text_value          TEXT,
    unit                TEXT,                 -- 'USD','percent','units','bps','shares'
    fiscal_period       TEXT,

    is_yoy_comparable   BOOLEAN DEFAULT TRUE,
    is_pro_forma        BOOLEAN DEFAULT FALSE,
    is_management_guidance BOOLEAN DEFAULT FALSE,

    source_fragment_id  TEXT REFERENCES evidence_fragment(fragment_id),
    source_doc_id       TEXT,
    extraction_date     TIMESTAMP,
    extraction_confidence FLOAT,

    data_version        INT DEFAULT 1,
    superseded_by       TEXT,

    fact_hash           TEXT UNIQUE,          -- ticker + metric_name + fiscal_period + value 的 hash
    created_at          TIMESTAMP DEFAULT NOW()
);
```

存储规则：
- 同一 ticker + metric + period 原则上只有一条 canonical entry。
- 新写入时检查 `fact_hash`，相同则跳过，冲突则进入 Fact Conflict Resolver。
- `superseded_by` 用于版本链，旧事实不删除。

### 6.5 Layer 4: Research Trace

```sql
CREATE TABLE research_trace (
    trace_id            TEXT PRIMARY KEY,
    timestamp           TIMESTAMP DEFAULT NOW(),
    agent_node          TEXT,
    action_type         TEXT,                 -- 'search','read','extract','compute','claim','write','review'
    action_detail       JSONB,
    hypothesis_id       TEXT,
    branch_id           TEXT,
    task_id             TEXT,
    section_id          TEXT,
    status              TEXT,                 -- 'success','failed','blocked','redundant'
    search_query        TEXT,
    source_urls         TEXT[],
    computation_code_hash TEXT,
    llm_model_used      TEXT,
    tokens_consumed     INT,
    duration_ms         INT
);
```

用途：
- 防止重复搜索相同关键词。
- 审计研究路径可复现性。
- Debug 漂移时回溯。
- Token / 成本统计。

### 6.6 关联表

```sql
-- 假设-证据关联
CREATE TABLE hypothesis_evidence_assoc (
    hypothesis_id       TEXT,
    fragment_id         TEXT REFERENCES evidence_fragment(fragment_id),
    relevance_score     FLOAT,
    is_contradicting    BOOLEAN DEFAULT FALSE,
    added_at            TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (hypothesis_id, fragment_id)
);

-- 假设-事实关联
CREATE TABLE hypothesis_fact_assoc (
    hypothesis_id       TEXT,
    fact_id             TEXT REFERENCES structured_fact(fact_id),
    role                TEXT,                 -- 'supporting','contradicting','context'
    added_at            TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (hypothesis_id, fact_id)
);

-- 分支关联（DAG 边）
CREATE TABLE branch_edge (
    edge_id             TEXT PRIMARY KEY,
    from_hypothesis_id  TEXT,
    to_hypothesis_id    TEXT,
    relation_type       TEXT,                 -- 'parent_child','refinement','contradiction','complement'
    created_at          TIMESTAMP DEFAULT NOW()
);
```

### 6.7 Knowledge Library（跨公司持久化知识库）

```sql
CREATE TABLE knowledge_entry (
    knowledge_id        TEXT PRIMARY KEY,
    knowledge_type      TEXT,                 -- 'valuation_principle','accounting_convention','industry_definition','regulatory_rule'
    category            TEXT,                 -- 'tech','financials','energy','healthcare'
    title               TEXT,
    content             TEXT,
    source              TEXT,
    version             INT,
    embedding           VECTOR(768),
    created_at          TIMESTAMP DEFAULT NOW()
);
```

存什么：
- 估值方法适用规则（什么时候用 PB、PE、PEG、SOTP、DCF）
- 行业特定知识（云业务 IaaS/PaaS/SaaS 拆分、半导体设计/制造/封测）
- 会计准则差异（US GAAP vs IFRS 收入确认）
- 研报写作规范（首页摘要格式、风险提示覆盖要求）
- 历史优秀研究报告的抽象经验（脱敏后的 claim 模式）

特征：
- 读写频率低，检索价值高。
- 离线 embedding，不需要高频向量搜索。
- 更像是 system prompt 的扩展，而非热数据路径。

### 6.8 Markdown Memory Mirror（人类可读研究笔记）

Markdown Memory 是四层结构化存储的 **人类可读镜像副本**，不是唯一真相源。

**用途：**

1. 方便人类分析师快速审阅研究进展
2. 方便 `git diff` 跟踪 Agent 每一轮修改了什么
3. 方便非技术人员理解研究过程
4. 最终报告的草稿从 markdown 目录拼装

**导出规则：**

```
research_memory/
├── documents_index.md              # Document Registry 的 markdown 镜像
├── evidence/                       # 每个 evidence fragment 一个文件
│   ├── fragment_E001.md
│   ├── fragment_E002.md
│   └── ...
├── facts/                          # Structured Fact 的表格形式
│   └── NVDA_facts.md
├── claims/                         # 每个 claim 一个文件（含 statement + 证据/反证列表）
│   ├── claim_CL001.md
│   └── ...
├── sections/                       # section 草稿（带版本）
│   ├── investment_focus_v1.md
│   ├── valuation_v2.md
│   └── ...
└── audit_trail.md                  # Research Trace 的事件日志
```

**每个 evidence fragment 的 markdown 格式：**

```markdown
# Evidence Fragment: E001
**Source:** doc_10k_NVDA_2024 (10-K)
**Type:** segment_revenue
**Reliability:** high
**Section in Source:** MD&A - Segment Results

> Data Center revenue increased 112% year over year to $47.5 billion...

---
*Extracted at: 2026-06-22T10:30:00Z*
*Confidence: 0.97*
```

**每个 claim 的 markdown 格式：**

```markdown
# Claim: CL001
**Type:** descriptive_claim
**Status:** verified
**Confidence:** 0.88

**Statement:**
Data Center is the primary revenue growth driver, with 112% YoY growth in FY2024.

**Supporting Evidence:**
- E001 (10-K, high reliability)
- E002 (Earnings Call Q4FY2024, high reliability)

**Supporting Computations:**
- C001 (segment_revenue_analysis, CAGR: 78%)

**Contradicting Evidence:**
- (none)
```

### 6.9 存储策略：什么存什么不存

| 数据 | 存不存 | 存在哪 | 理由 |
|---|---|---|---|
| 原始 10-K 全文 | 不存全文 | 存文件路径/URL | 不检索全文，只检索证据片段 |
| 被标记为 relevant 的段落 | 存 | Evidence Fragment + vector | 核心证据库 |
| 抽取后的数字 | 存 | Structured Fact | 精确查询用 |
| 未被任何 hypothesis 使用的段落 | 不存 | 不存 embedding | 无价值，增加噪声 |
| 搜索 query | 存 | Research Trace | 防止重复搜索 |
| 每个 computation 的代码 | 存 | Computation Store + hash | 可复现性 |
| LLM 推理的中间 chain-of-thought | 选择性存 | Research Trace | Debug 用 |
| 被 reject 的 hypothesis | 存 | Hypothesis 表 + status=rejected | 防止重复兜圈 |
| 上一个版本的财务数据 | 存 | 带 version 的 fact | 防止 stale data |
| 已完成报告的全文 | 存 | Report Store | 参考 |

---

## 7. 跨分支协同记忆与冲突仲裁

### 7.1 Cross-Branch Discovery Pool

```sql
CREATE TABLE cross_branch_discovery (
    discovery_id        TEXT PRIMARY KEY,
    source_branch_id    TEXT,
    source_hypothesis_id TEXT,
    content_type        TEXT,                 -- 'fact','observation','warning','counter_evidence','model_assumption'
    summary             TEXT,
    detail              TEXT,
    supporting_fragment_ids TEXT[],
    confidence          FLOAT,
    embedding           VECTOR(768),
    shared_at           TIMESTAMP DEFAULT NOW()
);
```

**共享触发规则：**

```python
def should_share_to_cross_branch(fragment, fact=None):
    # 规则1: 高可靠性结构化事实自动共享
    if fact and fact.extraction_confidence > 0.85 and fact.fact_type in (
        'revenue','segment_revenue','gross_margin','operating_margin','guidance'
    ):
        return True

    # 规则2: 被标记为反证的高可靠性摘录自动共享
    if fragment.source_reliability == 'high' and fragment.fragment_type in ('risk','guidance','competitor'):
        return True

    # 规则3: 含有关键管理层评论的摘录
    if fragment.fragment_type == 'guidance' and fragment.source_reliability in ('high','medium'):
        return True

    return False
```

**跨分支检索（协同记忆）：**

```python
def retrieve_cross_branch_discoveries(current_hypothesis, top_k=3):
    query_embedding = embed(current_hypothesis.statement)
    discoveries = search_cross_branch(query_embedding, top_k=top_k * 2)

    scored = []
    for d in discoveries:
        base_score = cosine_similarity(query_embedding, d.embedding)
        type_bonus = {'fact': 0.10, 'observation': 0.05, 'warning': 0.15, 'counter_evidence': 0.20}.get(d.content_type, 0)
        confidence_bonus = d.confidence * 0.05
        scored.append((d, base_score + type_bonus + confidence_bonus))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [d for d, _ in scored[:top_k]]
```

### 7.2 事实冲突仲裁

```sql
CREATE TABLE fact_conflict (
    conflict_id         TEXT PRIMARY KEY,
    ticker              TEXT,
    metric_name         TEXT,
    fiscal_period       TEXT,
    fact_id_a           TEXT REFERENCES structured_fact(fact_id),
    fact_id_b           TEXT REFERENCES structured_fact(fact_id),
    discrepancy_pct     FLOAT,
    conflict_type       TEXT,                 -- 'source_disagreement','gaap_vs_nongaap','stale_data'
    resolution          TEXT,
    resolution_rationale TEXT,
    resolved_at         TIMESTAMP
);
```

**仲裁优先级链：**

```
1. source_reliability:
   10-K > 10-Q > earnings_release > transcript > investor_presentation > news
2. 同源: 选更晚更新的版本
3. 同源同版本但数值不同: 标记 GAAP vs non-GAAP 问题，由 LLM 辅助判断
```

---

## 8. RAG 四种检索场景

### 8.1 场景一：证据检索 RAG

**用途：** 为假设验证检索相关证据摘录。

```python
def evidence_retrieval_rag(hypothesis, fragment_types=None, top_k=8):
    query = f"{hypothesis.statement} {hypothesis.key_value_drivers}"
    query_embedding = embed(query)

    fragments = pgvector_search(
        table="evidence_fragment",
        query_embedding=query_embedding,
        top_k=top_k,
        filters={
            "ticker": hypothesis.ticker,
            "fragment_type": fragment_types,
            "source_reliability": ["high", "medium"],
        }
    )

    # Hybrid rerank
    for f in fragments:
        f.hybrid_score = (
            0.50 * cosine_similarity(query_embedding, f.embedding)
            + 0.20 * reliability_weight(f.source_reliability)
            + 0.15 * recency_score(f.created_at)
            + 0.15 * type_match_score(f.fragment_type, hypothesis)
        )

    fragments.sort(key=lambda f: f.hybrid_score, reverse=True)
    return fragments[:top_k]
```

### 8.2 场景二：反证检索 RAG

**用途：** 主动寻找与假设矛盾的证据，保持 balanced view。

```python
def contradiction_retrieval_rag(hypothesis, top_k=5):
    contradiction_query = f"""
    Evidence that contradicts or challenges: {hypothesis.statement}
    Look for: risks, downside scenarios, management caution,
    competitive threats, margin pressure, demand slowdown.
    """
    query_embedding = embed(contradiction_query)

    fragments = pgvector_search(
        table="evidence_fragment",
        query_embedding=query_embedding,
        top_k=top_k * 2,
        filters={
            "ticker": hypothesis.ticker,
            "fragment_type": ["risk", "guidance", "competitor", "industry"],
        }
    )

    # 用 LLM 交叉验证是否真构成反证
    verified = []
    for f in fragments:
        if llm_contradiction_check(hypothesis, f.excerpt_text):
            verified.append(f)

    return verified[:top_k]
```

### 8.3 场景三：跨分支知识共享 RAG

**用途：** 从 Cross-Branch Discovery Pool 检索其他分支的发现。

```python
def cross_branch_rag(current_hypothesis, top_k=3):
    return retrieve_cross_branch_discoveries(current_hypothesis, top_k)
```

### 8.4 场景四：报告一致性 RAG

**用途：** Section 完成后，自检是否与其他 section 矛盾。

```python
def report_consistency_check(current_section, all_claims, all_facts):
    issues = []
    for claim in current_section.claims:
        similar = pgvector_search(table="claim_store", query_embedding=embed(claim.text), top_k=5)
        for sc in similar:
            if sc.section_id != current_section.section_id and llm_contradiction_check(claim, sc):
                issues.append(...)

    for fact in current_section.referenced_facts:
        latest = get_latest_fact(fact.ticker, fact.metric_name, fact.fiscal_period)
        if latest and latest.data_version > fact.data_version:
            issues.append(...)

    return issues
```

### 8.5 RAG 不能做的事（硬边界）

```
❌ 不要用 RAG 直接生成投资建议。
❌ 不要用 RAG 代替 Structured Fact 的 SQL 精确查询。
❌ 不要让 RAG 结果绕过 Claim Verification。
❌ 不要让 RAG 返回的低可靠性源覆盖高可靠性源。
❌ 不要让 RAG 自己裁决事实冲突。

✅ RAG 负责: 快速找到相关证据摘录。
✅ RAG 负责: 主动搜索反证。
✅ RAG 负责: 跨分支共享发现。
✅ RAG 负责: 报告内部一致性自检。
```

---

## 9. 券商研报结构约束

### 9.1 八段约束模板

```python
REPORT_TEMPLATE = {
    "1_investment_focus": {
        "title": "投资聚焦",
        "required_outputs": ["investment_rating", "target_price", "key_financial_summary_table",
                             "core_thesis_bullet_points", "catalyst_timeline"],
        "required_evidence_min": 3,
        "blocking_conditions": ["rating missing", "target_price missing", "rating_upside_mismatch"],
        "rating_thresholds": {
            "Buy": {"min_upside_pct": 0.15},
            "Outperform": {"min_upside_pct": 0.10},
            "Hold": {"min_upside_pct": -0.10, "max_upside_pct": 0.15},
            "Underperform": {"max_upside_pct": -0.05},
            "Sell": {"max_upside_pct": -0.10},
        },
    },
    "2_company_overview": {
        "title": "公司简介与发展历程",
        "required_outputs": ["ownership_structure", "management_background",
                             "historical_transformation_nodes", "business_segment_breakdown"],
        "required_evidence_min": 2,
    },
    "3_industry_and_competition": {
        "title": "行业分析与竞争格局",
        "required_outputs": ["tam_estimate", "industry_growth_rate", "value_chain_analysis",
                             "competitor_comparison_table", "competitive_position_assessment"],
        "required_evidence_min": 4,
    },
    "4_core_business_and_technology": {
        "title": "核心业务与技术分析",
        "required_outputs": ["technology_moat_assessment", "product_matrix", "competitive_advantage_analysis"],
        "required_evidence_min": 3,
    },
    "5_earnings_forecast": {
        "title": "盈利预测与关键假设",
        "required_outputs": ["segment_revenue_forecast_3y", "gross_margin_forecast",
                             "opex_forecast", "eps_forecast_3y", "key_assumptions_table"],
        "required_evidence_min": 5,
        "blocking_conditions": ["forecast_assumptions_lack_citations", "revenue_growth_exceeds_tam"],
    },
    "6_valuation": {
        "title": "估值分析与投资建议",
        "required_outputs": ["valuation_method_rationale", "peer_comparison_table",
                             "target_price_calculation", "sensitivity_analysis", "rating_explanation"],
        "required_evidence_min": 3,
        "blocking_conditions": ["valuation_method_not_justified", "target_price_missing",
                                "rating_inconsistent_with_upside"],
    },
    "7_risks": {
        "title": "风险提示",
        "required_outputs": ["company_specific_risks", "industry_risks", "macro_risks", "risk_mitigation_discussion"],
        "required_evidence_min": 2,
        "blocking_conditions": ["no_counter_evidence_for_thesis", "risks_are_generic_only"],
    },
    "8_financial_appendix": {
        "title": "财务报表附录",
        "required_outputs": ["income_statement_forecast", "balance_sheet_forecast", "cash_flow_statement_forecast"],
        "required_evidence_min": 0,
    },
}
```

### 9.2 Section Coverage 追踪

```python
@dataclass
class SectionCoverage:
    section_id: str
    required_outputs: list[str]
    completed_outputs: list[str]

    @property
    def coverage_score(self):
        return len(self.completed_outputs) / max(len(self.required_outputs), 1)

    def is_complete(self):
        return self.coverage_score >= 1.0

    def missing_outputs(self):
        return [o for o in self.required_outputs if o not in self.completed_outputs]
```

---

## 10. LangGraph 状态与流程设计

### 10.1 完整状态定义

```python
class EquityResearchState(TypedDict):
    # === 基础信息 ===
    ticker: str
    company_name: str
    sector: str
    industry: str
    report_type: str                    # 'initiation','update','thematic'
    time_horizon: str
    current_price: float
    currency: str

    # === 报告结构 ===
    report_template: list[dict]
    active_section_id: str | None
    section_coverage: dict[str, dict]
    completed_sections: list[str]

    # === 市场共识与 Alpha ===
    consensus_view: list[dict]
    expectation_gaps: list[dict]

    # === 假设 DAG ===
    hypothesis_nodes: dict[str, dict]
    active_hypothesis_ids: list[str]
    pruned_hypothesis_ids: list[str]
    verified_hypothesis_ids: list[str]

    # === 研究预算 ===
    research_phase: str                 # 'early','mid','late'
    research_budget: dict

    # === 证据 ===
    documents: list[dict]
    evidence_fragments: list[dict]
    contradiction_fragments: list[dict]

    # === 结构化数据 ===
    structured_facts: list[dict]
    fact_conflicts: list[dict]

    # === 业务与财务 ===
    business_drivers: list[dict]
    forecast_model: dict | None
    model_assumptions: list[dict]

    # === 估值 ===
    valuation_method: str | None
    valuation_model: dict | None
    target_price: float | None
    rating: str | None
    sensitivity_results: list[dict]

    # === Claims 与写作 ===
    claims: list[dict]
    section_drafts: dict[str, dict]
    final_report: str | None

    # === 协同记忆 ===
    cross_branch_discoveries: list[dict]

    # === 审计 ===
    research_traces: list[dict]
    warnings: list[str]
    errors: list[str]

    # === 元数据 ===
    started_at: str
    last_updated: str
    tokens_consumed: int
    api_calls: int
```

### 10.2 LangGraph 节点图

```
                        ┌─────────────────────┐
                        │   initialize_state   │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │   load_report_template│
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │ discover_consensus   │
                        └──────────┬──────────┘
                                   │
                        ┌──────────▼──────────┐
                        │ find_expectation_gaps│
                        └──────────┬──────────┘
                                   │
              ┌────────────────────▼────────────────────┐
              │           section_loop_router            │
              │  for each section in priority order:      │
              │  (2→3→4→5→6→7→1→8)                      │
              └────────────────────┬────────────────────┘
                                   │
                        ┌──────────▼──────────┐
                        │ generate_hypotheses  │◄─────────────┐
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ virtual_evaluate     │              │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ allocate_budget      │              │
                        └──────────┬──────────┘              │
                                   │                          │
              ┌────────────────────▼────────────────────┐     │
              │        hypothesis_loop_router            │     │
              │  for each accepted hypothesis:           │     │
              └────────────────────┬────────────────────┘     │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ retrieve_evidence    │              │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ check_cross_branch   │              │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ extract_facts        │              │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ resolve_fact_conflicts│             │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ run_computations     │              │
                        │ (proto → full)       │              │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ retrieve_contradictions│            │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ verify_claims        │              │
                        └──────────┬──────────┘              │
                                   │                          │
                        ┌──────────▼──────────┐              │
                        │ evaluate_stop_condition│            │
                        └──────────┬──────────┘              │
                                   │                          │
                          ┌────────┴────────┐                │
                          │ stop?            │                │
                          │ yes → continue   │                │
                          │ no ──────────────┘────────────────┘
                          │
                 ┌────────▼────────┐
                 │ share_to_cross_  │
                 │ branch_pool      │
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
                 │ write_section    │
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
                 │ review_section   │
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
                 │ consistency_rag  │
                 └────────┬────────┘
                          │
              ┌───────────┴───────────┐
              │ all sections complete? │
              │ yes ─────► no ─────► section_loop
              └───────────┬───────────┘
                          │
                 ┌────────▼────────┐
                 │ investment_      │
                 │ committee_review │
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
                 │ assemble_report  │
                 └────────┬────────┘
                          │
                 ┌────────▼────────┐
                 │      END        │
                 └─────────────────┘
```

### 10.3 路由逻辑

```python
def hypothesis_loop_router(state):
    active = [h for h in state["active_hypothesis_ids"]
              if state["hypothesis_nodes"][h]["status"] == "in_research"]
    if not active:
        return "write_section"

    budget = state["research_budget"]
    iterations = sum(1 for t in state["research_traces"] if t["hypothesis_id"] == active[0])
    if iterations >= budget["max_hypothesis_iterations"]:
        return "write_section"

    return "retrieve_evidence"


def section_loop_router(state):
    priority_order = [
        "2_company_overview", "3_industry_and_competition", "4_core_business_and_technology",
        "5_earnings_forecast", "6_valuation", "7_risks",
        "1_investment_focus", "8_financial_appendix",
    ]
    for section_id in priority_order:
        if section_id not in state["completed_sections"]:
            return section_id
    return "investment_committee_review"
```

---

## 11. 开发阶段：财务模型与估值

### 11.1 Progressive Financial Modeling

```python
class ProgressiveFinancialModeler:
    """
    两阶段财务建模:
    Stage 1: Prototype — rough revenue/EBIT/EPS + quick PE
    Stage 2: Full Model — segment-level 3-year forecast + full valuation
    """

    def prototype_model(self, facts, business_drivers):
        latest_revenue = get_latest_fact(facts, "total_revenue")
        recent_growth = compute_recent_cagr(facts, "total_revenue", periods=3)

        return PrototypeModel(
            revenue_growth_assumption=min(recent_growth * 0.8, 0.25),
            gross_margin=get_latest_fact(facts, "gross_margin").numeric_value,
            operating_margin=get_latest_fact(facts, "operating_margin").numeric_value,
            rough_eps=self._compute_rough_eps(latest_revenue, facts),
            model_confidence="low",
        )

    def full_model(self, facts, business_drivers, prototype, evidence):
        segments = []
        for driver in business_drivers:
            segment_forecast = self._forecast_segment(driver, facts, evidence, years=[1, 2, 3])
            segments.append(segment_forecast)

        return ForecastModel(
            segments=segments,
            consolidated_revenue=sum_segments(segments),
            consolidated_gross_margin=self._forecast_margin(segments, evidence),
            consolidated_opex=self._forecast_opex(facts, evidence),
            eps_forecast=self._compute_eps(segments),
            assumptions=[self._extract_assumptions(segments, evidence)],
        )
```

### 11.2 估值方法选择

```python
def select_valuation_method(company_profile, forecast, peers):
    # 多业务平台 → SOTP
    if len(forecast.segments) >= 3 and _segments_heterogeneous(forecast.segments):
        return ("SOTP", "Structurally different business segments with distinct growth and margin profiles.")

    # 重资产/周期性强 → PB
    if company_profile.get("asset_intensity") == "high" or company_profile.get("cyclicality") == "high":
        return ("PB", "Asset-heavy or cyclical business where book value provides a floor.")

    # 亏损高成长 → EV/Sales
    if forecast.eps_forecast[0] <= 0:
        return ("EV/Sales", "Company is currently unprofitable; revenue-based multiples are more appropriate.")

    # 稳定盈利 → PE
    if forecast.eps_growth_cagr < 0.20 and forecast.eps_forecast[0] > 0:
        return ("PE", "Stable profitability with moderate growth supports PE-based valuation.")

    # 高成长 SaaS → PEG
    if forecast.eps_growth_cagr >= 0.20 and company_profile.get("business_model") == "subscription":
        return ("PEG", "High-growth subscription model where PEG better captures growth-value trade-off.")

    return ("PE + DCF", "Multi-method cross-check for robustness.")
```

### 11.3 Claim 类型与验证标准

```python
CLAIM_TYPES = {
    "descriptive_claim": {
        "min_evidence": 1,
        "accepted_source_reliability": ["high"],
        "accepted_source_types": ["10-K", "10-Q", "earnings_release"],
    },
    "industry_claim": {
        "min_evidence": 2,
        "accepted_source_reliability": ["high", "medium"],
        "accepted_source_types": ["industry_report", "sec_filing", "transcript"],
    },
    "competitive_claim": {
        "min_evidence": 2,
        "accepted_source_reliability": ["high", "medium"],
        "requires_computation": True,
    },
    "driver_claim": {
        "min_evidence": 2,
        "requires_computation": True,
    },
    "forecast_claim": {
        "min_evidence": 2,
        "requires_computation": True,
        "requires_historical_basis": True,
    },
    "valuation_claim": {
        "min_evidence": 2,
        "requires_computation": True,
        "requires_peer_data": True,
    },
    "risk_claim": {
        "min_evidence": 1,
        "accepted_source_reliability": ["high", "medium"],
    },
    "recommendation_claim": {
        "requires_all": ["forecast", "valuation", "risk_assessment"],
        "min_evidence": 5,
    },
}
```

---

## 12. Perplexity API 集成

### 12.1 为什么用 Perplexity

```
优势:
- 原生支持实时搜索，不需要自己管理搜索引擎。
- 返回带引用的结构化结果，方便提取 source URL。
- 适合探索性搜索和初步信息获取。

限制:
- 不能替代 EDGAR / 官方 filing 的精确提取。
- 搜索结果可能有 hallucination，需要二次验证。

策略:
  Perplexity → 探索性搜索、初步了解、发现资料源
  EDGAR/Filing API → 精确事实提取、财务数据验证
```

### 12.2 三种搜索模式

```python
class SearchMode:
    EXPLORATORY = "exploratory"      # 广度优先，了解行业/公司
    TARGETED = "targeted"            # 假设锚定，找特定证据
    CONTRADICTION = "contradiction"  # 反证搜索

def search_perplexity(query, mode, focus="internet"):
    system_prompts = {
        "exploratory": "...",   # 探索性 prompt
        "targeted": "...",      # 精确证据 prompt
        "contradiction": "...", # 反证 prompt
    }

    response = perplexity_client.chat.completions.create(
        model="sonar-pro",
        messages=[
            {"role": "system", "content": system_prompts[mode]},
            {"role": "user", "content": query},
        ],
    )

    return {
        "answer": response.choices[0].message.content,
        "citations": response.citations,   # source URLs
    }
```

### 12.3 搜索计划生成

```python
def generate_search_plan(hypothesis, mode, budget):
    if mode == "exploratory":
        queries = [
            f"{hypothesis.ticker} business model and key revenue drivers",
            f"{hypothesis.ticker} industry competitive landscape market share",
            f"{hypothesis.ticker} recent earnings management guidance",
        ]
    elif mode == "targeted":
        queries = [f"{hypothesis.ticker} {et}" for et in hypothesis.required_evidence]
    elif mode == "contradiction":
        queries = [
            f"{hypothesis.ticker} challenges risks",
            f"{hypothesis.ticker} competitive threat downside",
        ]

    queries = queries[:budget.max_search_queries]
    return [SearchTask(query=q, hypothesis_id=hypothesis.hypothesis_id, mode=mode) for q in queries]
```

### 12.4 结果处理管道

```python
def process_perplexity_result(result, hypothesis_id, mode):
    # Step 1: 注册文档
    documents = [register_document(url=url, hypothesis_id=hypothesis_id) for url in result["citations"]]

    # Step 2: 提取段落 → Evidence Fragment
    fragments = []
    for para in split_into_paragraphs(result["answer"]):
        relevance = llm_relevance_score(para, hypothesis_id)
        if relevance > 0.3:
            fragments.append(EvidenceFragment(
                excerpt_text=para,
                fragment_type=classify_fragment_type(para),
                source_reliability=estimate_reliability_from_source(documents),
                extraction_confidence=relevance,
                cross_branch_shareable=(relevance > 0.7 and mode == "targeted"),
            ))

    return {"documents": documents, "fragments": fragments}
```

### 12.5 Perplexity 使用边界

```
✅ Perplexity 适合:
   - 行业概览搜索
   - 竞争对手初步了解
   - 管理层评论搜索
   - 寻找特定 filing 段落
   - 反证搜索
   - 市场共识/情绪初步判断

⚠️ Perplexity 需要二次确认:
   - 精确财务数字 → 验证: 直接读 filing
   - 管理层 guidance 数字 → 验证: 直接读 transcript
   - 市场份额数据 → 验证: 原始行业报告

❌ Perplexity 不能用于:
   - 作为唯一的数字来源写入报告
   - 代替 EDGAR API 的结构化数据提取
   - Fund flow / ownership / institutional data
```

---

## 13. Redis 角色

Redis 不是主存储，是 **热数据加速层**。五个角色：

### 13.1 Semantic Cache（语义缓存）

缓存 LLM 推理结果（假设评估、claim 验证、段落草稿），避免重复调用。

```
key: semcache:{ticker}:{section_id}:{hypothesis_statement_hash}
value: json.dumps(llm_result)
TTL: 900s (15 分钟，同一研究周期有效)
```

### 13.2 LangGraph Checkpoint 热缓存

LangGraph checkpoint 持久化存 PostgreSQL，热读写走 Redis。

```
key: state:{ticker}:{report_id}
value: json.dumps(state_summary)    # 精简版 state，不含大文本
TTL: 3600s
```

### 13.3 Perplexity / API Rate Limiter

滑动窗口速率限制。

```
key: rate:perplexity
method: INCR + EXPIRE 60
limit: MAX_CALLS_PER_MINUTE
```

### 13.4 Research Budget 原子计数器

多分支并行时，跨分支扣减全局预算，Redis 原子操作保证一致性。

```
key: budget:{ticker}:{report_id}:{resource}
value: remaining count
method: DECR
```

### 13.5 Cross-Branch Discovery Pool 热索引

pgvector 做精确检索，Redis 做 Top-K 热缓存。

```
key: crossbranch:{embedding_hash[:16]}
value: top_k_discovery_ids (JSON array)
TTL: 同一研究周期内有效
```

---

## 14. 评估体系

### 14.1 六层评估指标

```
Layer 1 — Retrieval Evaluation:
  source_recall_at_k         Top-K 结果覆盖了多少应有资料源
  evidence_relevance_at_k    证据相关比例
  authoritative_source_ratio  高可靠性源占比
  duplicate_source_rate       重复抓取率
  stale_source_rate           过期数据源比例

Layer 2 — Extraction Evaluation:
  fact_extraction_accuracy    抽取事实正确率
  numeric_accuracy             数值精度（误差 < 0.1%）
  date_accuracy                日期抽取正确率
  citation_accuracy            citation 指向正确位置的比例
  segment_kpi_mapping_accuracy Segment/Metric 匹配正确率

Layer 3 — Computation Evaluation:
  formula_correctness          计算公式正确率
  data_lineage_completeness    计算输入溯源完整性
  reproducibility_rate         可复现率
  financial_statement_consistency 预测表勾稽正确率
  chart_data_accuracy          图表是否准确反映底层数据

Layer 4 — Claim Evaluation:
  unsupported_claim_rate       未绑定证据的 claim 比例
  contradicted_claim_rate      存在反证的 claim 比例
  citation_coverage            完整 citation 的 claim 比例
  evidence_strength_mean       证据平均可靠性评分
  counter_evidence_coverage    核心 thesis 反证展示充分性

Layer 5 — Report Quality Evaluation:
  section_completeness         Required outputs 完成率
  thesis_coherence             首页 thesis 与正文一致性
  valuation_consistency        估值方法合理性 + 目标价/rating 一致性
  risk_balance                 风险部分充分性
  readability                  可读性
  sellside_style_alignment     券商研报格式匹配度

Layer 6 — End-to-End Evaluation:
  full_report_completion_rate  完整八段报告生成比例
  average_research_cost        平均 token / API cost
  average_runtime              端到端平均完成时间
  human_edit_distance          与人工修改版本的差异度
  analyst_acceptance_rate      分析师认为可用的比例
```

### 14.2 综合评分

```python
def compute_report_quality_score(state):
    # Hard Blockers
    blockers = []

    recommendation_claims = [c for c in state["claims"] if c["type"] == "recommendation_claim"]
    if any(c["status"] != "verified" for c in recommendation_claims):
        blockers.append("unsupported_recommendation")
    if state["target_price"] is None:
        blockers.append("missing_target_price")
    if state["rating"] and state["target_price"]:
        upside = (state["target_price"] - state["current_price"]) / state["current_price"]
        thresholds = state["report_template"]["1_investment_focus"]["rating_thresholds"][state["rating"]]
        if "min_upside_pct" in thresholds and upside < thresholds["min_upside_pct"]:
            blockers.append("rating_upside_mismatch")

    if blockers:
        return 0.0, blockers

    # Soft Scoring
    score = (
        0.20 * compute_thesis_strength(state)
        + 0.20 * compute_evidence_support(state)
        + 0.15 * compute_model_consistency(state)
        + 0.15 * compute_valuation_reasonableness(state)
        + 0.10 * compute_risk_balance(state)
        + 0.10 * compute_section_completeness(state)
        + 0.10 * compute_citation_integrity(state)
    )

    return score, []
```

---

## 15. MVP 定义与实施路线

### 15.1 MVP v1：Hypothesis-Driven Mini Report

**范围：** 单一 ticker，最小可行研究闭环。

**Report Sections：**

```
✅ company_overview
✅ industry_and_competition
✅ earnings_forecast (简化版)
✅ valuation (PE/EV multiples) (via tools, but don't implement yet. make a mock one)
✅ risks
✅ investment_focus (最后生成)
❌ core_business_and_technology (推迟 v2)
❌ financial_appendix (推迟 v2)
```

**技术栈 v1：**

```
LangGraph:         Agent 编排
Perplexity API:    探索性搜索 + 初步证据
EDGAR/SEC API:     Filing 精确获取
Yahoo Finance:     股价 + 基础财务
PostgreSQL:        Document Registry + Structured Fact
pgvector:          Evidence Fragment 向量检索
Qwen Embedding:    本地 embedding
Python Executor:   财务计算 + 图表生成
Redis:             热缓存 + Rate Limiter + Budget Counter
Markdown Export:   人类可读研究笔记
```

**Agent 实现清单（按开发顺序）：**

| 阶段 | Agent | 职责 |
|---|---|---|
| 0 | initialize_state | 填充 ticker / report_type |
| 0 | template_controller | 加载模板约束 |
| 1 | retrieve_evidence | Perplexity + 官方源 → fragments |
| 1 | extract_facts | 从 fragments 抽取数值 → facts |
| 1 | verify_claim | 检查 claim 的 evidence + fact 支撑 |
| 1 | store_trace | 全过程记录 |
| 2 | generate_hypotheses | 生成 3-5 个假设 |
| 2 | virtual_evaluate | LLM 评分 |
| 2 | write_section | verified claims → 段落 |
| 2 | review_section | 完整性检查 |
| 3 | business_driver_decomp | 拆解驱动 |
| 3 | financial_forecast | rough EPS + PE |
| 3 | valuation | 选择估值法 + 目标价 |
| 3 | chart_generation | matplotlib 图表 |
| 4 | consensus_discovery | 市场共识提取 |
| 4 | expectation_gap_finder | 预期差识别 |
| 4 | investment_committee_review | 硬性检查 + 评分 |
| 4 | report_assembler | 拼装完整报告 |
| 4 | markdown_memory_export | 导出人类可读副本 |
| 5 | section_loop_router | 自动调度 section |
| 5 | hypothesis_loop_router | 假设循环控制 |
| 5 | budget_manager | 限制搜索/阅读/计算预算 |

**验收标准：**

```
1. 输入 ticker，输出 6 段 mini report
2. 每个 claim 有 evidence 或 computation 支撑
3. 首页 rating 和目标价与正文一致
4. 至少 1 个预期差假设被成功验证
5. 无 unsupported recommendation claim
6. 所有引用可追溯到 registered document
7. 端到端完成时间 < 30 分钟
8. Structured Fact 精确提取正确率 > 85%
```

### 15.2 MVP v2：Full Sell-Side Draft

**新增：**

```
- 4_core_business_and_technology
- 8_financial_appendix
- 完整三表预测
- DCF + SOTP 估值
- Sensitivity table
- 多 ticker peer comparison
- Dynamic budget allocation
- Adaptive DAG pruning
- 完整 Cross-Branch Discovery Pool
```

### 15.3 MVP v3：Production Research System

**新增：**

```
- 多轮 earnings 更新后自动刷新报告
- Human-in-the-loop analyst editing
- Report version control
- Skill marketplace（可插拔）
- Multi-ticker thematic research
- 报告质量自动评分
- 历史报告库 + 脱敏知识积累
- 完整的评估体系
```

### 15.4 实施时间线

```
step 1-2:   LangGraph 骨架 + State Schema + 单节点串联
step 3:     Perplexity API 集成 + Document Registry + Evidence Fragment 存储
step 4:     Consensus + Hypothesis Generator + Virtual Evaluation
step 5:     Extraction Agent + Structured Fact Store
step 6:     Business Driver + Financial Forecast (prototype)
step 7:     Valuation Agent + Claim Verification
step 8:     Section Writer + Section Reviewer
step 9:     Report Assembler + Investment Committee Review
step 10:    End-to-end 调试 + 评测集构建 + 验收
```

---

## 附录 A：核心 Claim 类型定义

```python
class ClaimType(str, Enum):
    DESCRIPTIVE = "descriptive_claim"
    INDUSTRY = "industry_claim"
    COMPETITIVE = "competitive_claim"
    DRIVER = "driver_claim"
    FORECAST = "forecast_claim"
    VALUATION = "valuation_claim"
    RISK = "risk_claim"
    RECOMMENDATION = "recommendation_claim"


class ClaimStatus(str, Enum):
    PROPOSED = "proposed"
    VERIFIED = "verified"
    PARTIALLY_SUPPORTED = "partially_supported"
    UNSUPPORTED = "unsupported"
    CONTRADICTED = "contradicted"
    NEEDS_MORE_RESEARCH = "needs_more_research"


@dataclass
class Claim:
    claim_id: str
    hypothesis_id: str
    section_id: str
    claim_type: ClaimType
    text: str
    status: ClaimStatus
    confidence: float
    supporting_evidence_ids: list[str]
    supporting_computation_ids: list[str]
    contradicting_evidence_ids: list[str]
    is_core_thesis: bool
    created_at: datetime
```

## 附录 B：Hypothesis Node 完整 Schema

```python
@dataclass
class HypothesisScores:
    materiality: float
    variant_perception: float
    model_linkage: float
    verifiability: float
    evidence_availability: float
    novelty: float
    research_cost: float
    priority: float       # computed


@dataclass
class HypothesisNode:
    hypothesis_id: str
    parent_id: str | None
    children_ids: list[str]
    ticker: str
    section_targets: list[str]

    statement: str
    consensus_view: str
    variant_view: str
    key_value_drivers: list[str]
    required_evidence: list[str]
    required_computation: list[str]
    valuation_link: str

    status: str            # proposed|accepted|in_research|verified|rejected|needs_more_research
    scores: HypothesisScores
    evidence_strength: float
    contradiction_risk: float

    research_iterations: int
    max_iterations: int
    supporting_evidence_ids: list[str]
    contradicting_evidence_ids: list[str]
    computation_results: dict | None

    created_at: datetime
    updated_at: datetime
```

---

*文档版本：v2.1*  
*最后更新：2026-06-22*
