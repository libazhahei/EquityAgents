可以。你的目标其实不是“把 LangGraph 节点换成 Agent”，而是要把系统升级成一个 **Hybrid Research System**：

> **Workflow 负责研究流程的确定性、质量门控和交付顺序；Agent 负责开放式研究、假设探索、证据发现和推理；Tools 负责可验证的数据获取、计算、检索和制图；Skills 负责把某类专业研究能力封装成可复用模块。**

也就是说，你未来的系统应该长这样：

```text
User Mandate
   ↓
Research Workflow Spine
   ↓
Lead Analyst Agent
   ↓
Skill Registry
   ↓
Tools / Data APIs / Search / Calculators / Models
   ↓
Evidence / Claim / Assumption Ledgers
   ↓
Quality Gates
   ↓
Professional Equity Report
```

下面我给你一个完整的设计建议。

---

# 1. 先明确几个概念

你现在的系统里有很多 `create_xxx_agent`，但它们其实更像 workflow node。未来建议区分四层：

---

## 1.1 Workflow：确定性流程

Workflow 适合处理：

- 初始化；
- 加载模板；
- 文档 ingestion；
- 共识提取；
- 研究计划生成；
- 财务模型构建；
- 估值计算；
- 投委会审查；
- 最终 QA；
- 导出。

这些地方有明确顺序、明确输入输出、明确质量门槛。

例如：

```text
discover_consensus → find_expectation_gaps → generate_research_plan
```

这就是 workflow。

---

## 1.2 Agent：自主研究者

Agent 适合处理：

- 根据问题自主制定检索策略；
- 发现预期差；
- 生成投资假设；
- 找支持证据和反证；
- 判断哪些数据更重要；
- 追问“为什么市场错了”；
- 决定是否需要继续研究；
- 对 thesis 进行自我批判。

Agent 不应该只是“写一段文本”，而应该像 analyst 一样：

```text
提出假设 → 找证据 → 找反证 → 修改假设 → 形成判断
```

---

## 1.3 Tools：低层工具

Tools 应该尽量 deterministic，职责单一。

例如：

- `search_sec_filings`
- `retrieve_annual_report`
- `extract_table_from_pdf`
- `get_market_price`
- `get_consensus_estimates`
- `calculate_ev_ebitda`
- `run_dcf`
- `plot_revenue_margin_chart`
- `store_evidence`
- `fetch_broker_report_metadata`

Tools 不应该自己做复杂投资判断。

---

## 1.4 Skills：专业能力模块

Skill 介于 Agent 和 Tool 之间。

它不是单个工具，而是一套“专业研究动作”。

比如：

- `BrokerConsensusMiningSkill`
- `VariantViewDiscoverySkill`
- `BusinessModelAnalysisSkill`
- `HistoricalFinancialAnalysisSkill`
- `ForecastAssumptionBuilderSkill`
- `ValuationSkill`
- `RiskToThesisMappingSkill`

Skill 可以调用多个 tools，也可以包含 LLM reasoning，但必须有：

- 输入 schema；
- 输出 schema；
- 工具权限；
- 停止条件；
- 质量检查；
- 可追踪证据。

---

# 2. 推荐总体架构

我建议你设计成下面这种架构。

```text
┌────────────────────────────────────────────┐
│                 User Request                │
│  ticker, company, scope, report_type, style │
└─────────────────────┬──────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│              Workflow Spine                 │
│  deterministic orchestration and gates       │
└─────────────────────┬──────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│              Lead Analyst Agent             │
│  plans research, invokes skills, critiques   │
└─────────────────────┬──────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│                Skill Registry               │
│  reusable professional research capabilities │
└─────────────────────┬──────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│                 Tool Layer                  │
│ search, data, parser, calculator, charting   │
└─────────────────────┬──────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│         Research Memory / Ledgers           │
│ claims, evidence, assumptions, metrics       │
└─────────────────────┬──────────────────────┘
                      ↓
┌────────────────────────────────────────────┐
│           Report Assembly + QA              │
└────────────────────────────────────────────┘
```

---

# 3. 核心思想：Workflow 是骨架，Agent 是研究大脑，Skills 是专业能力，Tools 是手脚

你的目标是“研报尽可能专业以及有深度”，所以不要把每个章节写死成简单 workflow。

更好的方式是：

```text
Workflow 决定必须完成哪些研究阶段
Agent 决定每个阶段怎么研究
Skill 提供专业研究方法
Tool 提供数据和计算能力
Quality Gate 决定是否允许进入下一阶段
```

---

# 4. 哪些地方应该继续用 Workflow？

我建议这些地方保留 workflow。

---

## 4.1 初始化与任务定义

```text
initialize_state
→ load_report_template
→ define_research_mandate
```

这里要明确：

- 股票代码；
- 市场；
- 货币；
- 当前价格日期；
- 报告类型：initiation / update / earnings preview / earnings review；
- 投资周期：6 个月 / 12 个月；
- 目标读者；
- 输出格式；
- 允许的数据源；
- 是否允许使用 broker reports；
- 是否需要 human approval。

---

## 4.2 数据 ingestion

```text
ingest_documents
→ parse_documents
→ build_source_index
```

这是确定性强的部分。

输入包括：

- 年报；
- 季报；
- 电话会 transcript；
- investor presentation；
- broker reports；
- 行业报告；
- 新闻；
- 市场数据；
- 财务数据库。

输出应该是 source index：

```python
{
    "source_id": "SRC_001",
    "source_type": "10-K",
    "title": "FY2025 Annual Report",
    "date": "2026-02-15",
    "publisher": "Company",
    "reliability": 0.95,
    "path": "...",
}
```

---

## 4.3 共识和预期差

```text
extract_broker_views
→ discover_consensus
→ find_expectation_gaps
```

这是 equity research 的核心起点。

你不是在写百科，而是在回答：

> 市场现在怎么看？  
> 我们和市场哪里不一样？  
> 市场可能错在哪里？

---

## 4.4 财务模型和估值

这里也应该 workflow 化，因为它有强计算约束。

```text
historical_financials
→ normalize_financials
→ operating_kpi_extraction
→ forecast_assumption_building
→ financial_forecast
→ valuation
→ sensitivity_analysis
→ rating_target_price_check
```

LLM 可以解释逻辑，但数字最好由 deterministic Python 完成。

---

## 4.5 投委会审核与最终 QA

```text
investment_committee_review
→ final_consistency_check
→ compliance_check
→ export
```

这些是 gate，不应该完全自由发挥。

---

# 5. 哪些地方应该让 Agent 自主研究？

下面这些地方应该 agentic。

---

## 5.1 投资假设生成

不要让系统直接按模板写：

```text
Company Overview
Industry
Forecast
Valuation
Risk
```

而是先让 Agent 做：

```text
What could matter for the stock?
```

例如：

- 市场是否低估新业务增长？
- 毛利率是否可能超预期修复？
- 行业价格战是否被高估？
- 管理层指引是否保守？
- 估值折价是否合理？
- 资产负债表风险是否被忽略？
- 政策变化是否形成 catalyst？

---

## 5.2 证据探索

Agent 应该能自主决定：

- 去查年报还是电话会？
- 去查行业数据还是竞品数据？
- 是否需要 broker reports 对比？
- 是否需要找反证？
- 当前证据是否足够？
- 哪个假设更值得深入？

---

## 5.3 反证搜索

专业研报一定要有 skeptical thinking。

Agent 应该主动问：

```text
What would prove this thesis wrong?
```

例如：

- 如果我们的 margin expansion thesis 是错的，最可能因为什么？
- 是否有管理层表述反驳？
- 是否有竞品降价迹象？
- 是否有库存或订单数据恶化？
- 是否有 sell-side analyst 持相反观点？

---

## 5.4 章节研究

每个章节不是直接写，而是一个研究 loop：

```text
section objective
→ generate sub-questions
→ retrieve evidence
→ extract facts
→ verify claims
→ write section
→ review section
→ if fail, research more
```

---

# 6. 推荐的新版 Workflow Spine

你可以把主流程改成这样：

```text
initialize_state
→ load_report_template
→ define_research_mandate
→ ingest_documents
→ build_source_index

→ extract_broker_views
→ discover_consensus
→ find_expectation_gaps

→ generate_research_plan
→ autonomous_research_loop

→ historical_financial_workflow
→ forecast_workflow
→ valuation_workflow
→ scenario_sensitivity_workflow

→ risk_to_thesis_mapping
→ catalyst_monitor

→ investment_committee_review
    ↳ if fail: back to research / forecast / valuation

→ write_investment_focus
→ plan_tables_and_charts
→ generate_charts
→ assemble_report
→ final_consistency_check
→ compliance_check
→ export_report
```

重点是中间这块：

```text
generate_research_plan → autonomous_research_loop
```

不要写死所有研究动作，而是让 Lead Analyst Agent 调用 skills。

---

# 7. Agent 设计：建议先做一个 Lead Analyst Agent，而不是一堆 Agent

你现在可能会想做很多 agent：

- industry agent；
- valuation agent；
- risk agent；
- writer agent；
- reviewer agent。

但我建议 MVP 阶段先不要过度 multi-agent。先做一个强的：

```text
LeadAnalystAgent
```

它可以调用不同 skills。

原因：

1. 多 agent 容易产生状态不一致；
2. 多 agent 会增加 routing 复杂度；
3. 专业研报最怕 thesis 不统一；
4. 一个 Lead Analyst 更容易维持统一投资判断。

未来可以逐步拆成：

- Lead Analyst；
- Evidence Analyst；
- Financial Modeling Analyst；
- Valuation Analyst；
- Skeptic Analyst；
- Editor / Compliance Analyst。

但初期推荐：

```text
One Lead Agent + Skill Registry + Tool Layer
```

---

# 8. Lead Analyst Agent 的职责

Lead Analyst Agent 应该做这些事：

```python
LeadAnalystAgent:
    - understand mandate
    - generate research plan
    - prioritize research questions
    - select skills
    - call tools through skills
    - maintain thesis ledger
    - update evidence ledger
    - challenge its own thesis
    - decide when evidence is sufficient
    - request deterministic financial modeling
    - synthesize report sections
    - respond to IC review feedback
```

它不应该直接伪造数字，也不应该自己算复杂估值。

---

# 9. Tools 设计

Tools 应该是低层能力，尽量小而确定。

---

## 9.1 Data Retrieval Tools

```python
search_web
search_company_filings
search_transcripts
search_broker_reports
search_news
search_industry_reports
search_internal_vector_db
```

---

## 9.2 Document Parsing Tools

```python
parse_pdf
extract_tables
extract_financial_statements
extract_management_guidance
extract_segment_breakdown
extract_kpi_mentions
```

---

## 9.3 Market and Financial Data Tools

```python
get_current_price
get_market_cap
get_share_count
get_enterprise_value
get_historical_prices
get_financial_statements
get_consensus_estimates
get_peer_multiples
get_ownership_data
```

---

## 9.4 Calculation Tools

```python
calculate_cagr
calculate_margin
calculate_roic
calculate_wacc
calculate_dcf
calculate_trading_multiple_valuation
calculate_sotp
calculate_sensitivity_table
calculate_total_return
```

---

## 9.5 Evidence and Memory Tools

```python
store_evidence
store_claim
store_assumption
link_evidence_to_claim
link_assumption_to_forecast
retrieve_claims_by_section
retrieve_contradictory_evidence
```

---

## 9.6 Charting Tools

```python
plot_revenue_by_segment
plot_margin_trend
plot_peer_multiple_comparison
plot_dcf_sensitivity
plot_consensus_bridge
```

---

# 10. Skill 设计

Skill 是你未来扩展系统的关键。

建议每个 Skill 都有统一接口。

---

## 10.1 Skill Interface

可以设计成这样：

```python
from typing import Protocol, Any
from pydantic import BaseModel

class SkillInput(BaseModel):
    mandate: dict
    state_snapshot: dict
    objective: str
    constraints: dict | None = None

class SkillOutput(BaseModel):
    summary: str
    claims: list[dict]
    evidence_ids: list[str]
    assumptions: list[dict] = []
    confidence: float
    data_quality_flags: list[str] = []
    next_questions: list[str] = []

class Skill(Protocol):
    name: str
    description: str
    allowed_tools: list[str]
    output_schema: type[SkillOutput]

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        ...
```

---

## 10.2 Skill Manifest

每个 skill 还应该有 manifest：

```python
{
    "name": "broker_consensus_mining",
    "description": "Extract and compare sell-side broker views.",
    "trigger": [
        "consensus needed",
        "variant view needed",
        "broker reports available"
    ],
    "required_inputs": [
        "ticker",
        "broker_reports",
        "current_price"
    ],
    "outputs": [
        "rating_distribution",
        "target_price_range",
        "eps_consensus",
        "key_debate_points",
        "bull_bear_split"
    ],
    "allowed_tools": [
        "search_broker_reports",
        "parse_pdf",
        "extract_tables",
        "store_evidence"
    ],
    "quality_gates": [
        "at least 3 broker reports if available",
        "target price date required",
        "rating date required",
        "source citation required"
    ]
}
```

这样以后你加 skill 很容易。

---

# 11. 第一批应该实现的 Skills

我建议先做下面这些。

---

## 11.1 `CompanyUnderstandingSkill`

目标：理解公司是谁、怎么赚钱。

输出：

- business description；
- segment breakdown；
- geography breakdown；
- revenue model；
- key products；
- customer base；
- management；
- ownership。

---

## 11.2 `BrokerConsensusMiningSkill`

目标：看市场怎么看。

输出：

- broker rating distribution；
- target price range；
- consensus EPS；
- consensus revenue；
- most bullish view；
- most bearish view；
- key debate points。

---

## 11.3 `VariantViewDiscoverySkill`

目标：找预期差。

输出：

- where we differ from consensus；
- evidence supporting variant view；
- possible mispricing；
- key stock debates；
- what market may be missing。

这是专业 equity research 的灵魂。

---

## 11.4 `BusinessModelAnalysisSkill`

目标：分析商业模式和 unit economics。

输出：

- revenue drivers；
- pricing mechanism；
- volume / ASP / mix；
- customer retention；
- margin drivers；
- operating leverage；
- unit economics。

---

## 11.5 `IndustryCompetitionSkill`

目标：行业和竞争格局。

输出：

- TAM；
- market growth；
- value chain；
- market share；
- pricing trend；
- competition intensity；
- barriers to entry；
- regulatory factors。

---

## 11.6 `HistoricalFinancialAnalysisSkill`

目标：解释过去的财务表现。

输出：

- revenue CAGR；
- segment growth；
- gross margin trend；
- operating margin trend；
- FCF conversion；
- working capital；
- ROE / ROIC；
- leverage；
- capital intensity。

---

## 11.7 `OperatingKPIExtractionSkill`

目标：抽取建模所需 KPI。

不同行业不同 KPI。

例如：


| 行业   | KPI                                              |
| ---- | ------------------------------------------------ |
| SaaS | ARR, NRR, churn, CAC, LTV                        |
| 电商   | GMV, take rate, AOV, MAU                         |
| 银行   | NIM, NPL, loan growth, CASA                      |
| 新能源  | shipment, ASP, unit margin, capacity utilization |
| 半导体  | wafer starts, ASP, utilization, backlog          |
| 消费   | volume, ASP, channel inventory, SSSG             |


---

## 11.8 `ForecastAssumptionSkill`

目标：把业务驱动转成预测假设。

输出：

- segment revenue assumptions；
- gross margin assumptions；
- opex assumptions；
- capex assumptions；
- working capital assumptions；
- tax rate；
- share count；
- EPS bridge；
- assumptions vs consensus。

---

## 11.9 `ValuationSkill`

目标：估值。

注意：这个 skill 应该调用 deterministic valuation tools，而不是让 LLM 随便生成 target price。

输出：

- valuation method；
- peer set；
- trading multiples；
- DCF assumptions；
- SOTP if needed；
- target price；
- implied upside；
- rating；
- sensitivity table。

---

## 11.10 `RiskCounterThesisSkill`

目标：找反证和风险。

输出：

- risk-to-thesis mapping；
- downside scenario；
- leading indicators；
- what would change our view；
- counter-evidence；
- thesis failure points。

---

## 11.11 `CatalystMonitoringSkill`

目标：未来跟踪什么。

输出：

- earnings date；
- product launch；
- policy events；
- capacity ramp；
- data releases；
- investor day；
- KPI to monitor；
- thesis linkage。

---

## 11.12 `SectionWritingSkill`

目标：把研究结果写成专业研报语言。

要求：

- 不新增未经验证的数据；
- 每个关键 claim 有 citation；
- 用投资语言表达；
- 结构清晰；
- 与 thesis 一致。

---

## 11.13 `QualityReviewSkill`

目标：检查报告质量。

检查：

- claim 是否有 evidence；
- 数字是否一致；
- rating 和 upside 是否匹配；
- risk 是否具体；
- forecast 是否有依据；
- valuation 是否可复现；
- 是否存在 hallucinated source；
- 是否存在 stale data。

---

# 12. 三个 Ledger 是专业化的核心

你未来一定要有三个核心 ledger。

---

## 12.1 Evidence Ledger

记录所有证据。

```python
{
    "evidence_id": "EVID_001",
    "source_id": "SRC_001",
    "source_type": "Annual Report",
    "date": "2026-03-01",
    "page": 42,
    "quote": "Revenue from cloud segment increased by 28% YoY.",
    "metric": "cloud revenue growth",
    "value": "28%",
    "period": "FY2025",
    "reliability_score": 0.95,
    "freshness_score": 0.90
}
```

---

## 12.2 Claim Ledger

记录报告里的每个重要判断。

```python
{
    "claim_id": "CLM_001",
    "section": "investment_thesis",
    "claim": "Cloud segment growth is likely to exceed consensus expectations.",
    "claim_type": "variant_view",
    "direction": "positive",
    "supporting_evidence": ["EVID_001", "EVID_008"],
    "contradicting_evidence": ["EVID_014"],
    "confidence": 0.74,
    "status": "verified"
}
```

---

## 12.3 Assumption Ledger

记录预测和估值假设。

```python
{
    "assumption_id": "ASM_001",
    "metric": "FY2026 cloud revenue growth",
    "our_assumption": "24%",
    "consensus": "18%",
    "difference": "+600bps",
    "rationale": "Backlog growth and management commentary indicate faster enterprise adoption.",
    "evidence_ids": ["EVID_001", "EVID_009"],
    "sensitivity": "high",
    "used_in": ["financial_forecast", "dcf", "target_price"]
}
```

这三个 ledger 能让你的研报变得：

- 可验证；
- 可追踪；
- 可复用；
- 可审计；
- 可被专业分析师信任。

---

# 13. Agent 自主研究 Loop 应该怎么设计？

你可以把核心 autonomous research node 设计成一个 mini-loop。

```text
Research Objective
   ↓
Generate Questions
   ↓
Select Skill
   ↓
Use Tools
   ↓
Extract Evidence
   ↓
Update Ledgers
   ↓
Critique Findings
   ↓
Need More Research?
   ↓
Stop / Continue
```

伪代码：

```python
while budget.remaining() > 0:
    research_gap = agent.identify_most_important_gap(state)

    selected_skill = agent.select_skill(
        objective=research_gap,
        available_skills=skill_registry
    )

    skill_output = selected_skill.run(
        input=SkillInput(
            mandate=state.mandate,
            state_snapshot=state.snapshot(),
            objective=research_gap
        ),
        tools=tool_registry
    )

    state.update_ledgers(skill_output)

    review = agent.critique(skill_output, state)

    if review.is_sufficient:
        break

    if review.needs_different_skill:
        continue

    if review.needs_human:
        route_to_human()
```

---

# 14. 怎么避免 Agent 太自由导致胡说？

你需要几个硬约束。

---

## 14.1 Tool Permission

不同 skill 只能调用指定 tools。

例如 ValuationSkill：

```python
allowed_tools = [
    "get_current_price",
    "get_financial_statements",
    "get_peer_multiples",
    "calculate_dcf",
    "calculate_trading_multiple_valuation",
    "calculate_sensitivity_table"
]
```

不能随便 web search 后直接编 target price。

---

## 14.2 Evidence Required

每个核心 claim 必须链接 evidence。

```python
if claim.importance == "high" and len(claim.supporting_evidence) < 2:
    fail_review()
```

---

## 14.3 Contradiction Required

每个核心 investment thesis 必须有反证搜索。

```python
if thesis.has_no_counter_evidence_search:
    fail_review()
```

---

## 14.4 Deterministic Calculation

以下内容必须由工具计算：

- target price；
- upside；
- EPS；
- CAGR；
- margins；
- EV；
- multiples；
- DCF；
- sensitivity；
- peer median。

LLM 只能解释，不能直接生成最终数字。

---

## 14.5 Data Freshness

每个关键数据都需要 as-of date。

```python
{
    "metric": "current_price",
    "value": 125.3,
    "as_of": "2026-06-22"
}
```

否则专业分析师不会信。

---

# 15. 推荐新版 LangGraph 结构

你可以把 graph 改成“workflow spine + autonomous node”。

示意：

```python
g.set_entry_point("initialize_state")

g.add_edge("initialize_state", "load_report_template")
g.add_edge("load_report_template", "define_research_mandate")
g.add_edge("define_research_mandate", "ingest_documents")
g.add_edge("ingest_documents", "build_source_index")

g.add_edge("build_source_index", "extract_broker_views")
g.add_edge("extract_broker_views", "discover_consensus")
g.add_edge("discover_consensus", "find_expectation_gaps")

g.add_edge("find_expectation_gaps", "generate_research_plan")
g.add_edge("generate_research_plan", "autonomous_research")

g.add_conditional_edges(
    "autonomous_research",
    research_completion_router,
    {
        "continue_research": "autonomous_research",
        "financial_model": "historical_financials",
        "human_review": "human_review",
    },
)

g.add_edge("historical_financials", "operating_kpi_extraction")
g.add_edge("operating_kpi_extraction", "forecast_assumptions")
g.add_edge("forecast_assumptions", "financial_forecast")
g.add_edge("financial_forecast", "forecast_consistency_check")

g.add_conditional_edges(
    "forecast_consistency_check",
    forecast_router,
    {
        "pass": "valuation",
        "revise_assumptions": "forecast_assumptions",
        "more_research": "autonomous_research",
    },
)

g.add_edge("valuation", "scenario_sensitivity")
g.add_edge("scenario_sensitivity", "rating_target_price_check")

g.add_conditional_edges(
    "rating_target_price_check",
    valuation_router,
    {
        "pass": "risk_to_thesis_mapping",
        "revise_valuation": "valuation",
        "revise_forecast": "forecast_assumptions",
    },
)

g.add_edge("risk_to_thesis_mapping", "catalyst_monitor")
g.add_edge("catalyst_monitor", "investment_committee_review")

g.add_conditional_edges(
    "investment_committee_review",
    ic_review_router,
    {
        "approve": "write_investment_focus",
        "more_research": "autonomous_research",
        "revise_forecast": "forecast_assumptions",
        "revise_valuation": "valuation",
        "human_review": "human_review",
    },
)

g.add_edge("write_investment_focus", "write_remaining_sections")
g.add_edge("write_remaining_sections", "plan_tables_and_charts")
g.add_edge("plan_tables_and_charts", "chart_generation")
g.add_edge("chart_generation", "assemble_report")
g.add_edge("assemble_report", "final_consistency_check")
g.add_edge("final_consistency_check", "compliance_check")
g.add_edge("compliance_check", "export_report")
g.add_edge("export_report", END)
```

这个结构的好处是：

- 关键阶段是 workflow；
- 研究阶段是 autonomous；
- 财务和估值是 deterministic；
- 审查节点可以打回；
- 最终报告有质量控制。

---

# 16. `autonomous_research` 内部怎么实现？

你可以让它不是一个普通 agent，而是一个 agent runtime。

```python
class AutonomousResearchRuntime:
    def __init__(self, lead_agent, skill_registry, tool_registry):
        self.lead_agent = lead_agent
        self.skill_registry = skill_registry
        self.tool_registry = tool_registry

    def run(self, state):
        objective = self.lead_agent.pick_next_research_objective(state)

        skill_name = self.lead_agent.select_skill(
            objective=objective,
            state=state,
            available_skills=self.skill_registry.list()
        )

        skill = self.skill_registry.get(skill_name)

        output = skill.run(
            input=SkillInput(
                mandate=state["mandate"],
                state_snapshot=state,
                objective=objective
            ),
            tools=self.tool_registry.for_skill(skill_name)
        )

        state = update_ledgers(state, output)

        critique = self.lead_agent.critique_research_output(
            objective=objective,
            output=output,
            state=state
        )

        state["research_status"] = critique.next_status
        state["research_gaps"] = critique.remaining_gaps

        return state
```

---

# 17. State 设计建议

你的 `EquityResearchState` 应该扩展成更像研究数据库。

```python
class EquityResearchState(TypedDict):
    mandate: dict
    report_template: dict

    source_index: list[dict]
    broker_views: list[dict]
    consensus: dict
    expectation_gaps: list[dict]

    research_plan: dict
    active_objective: str
    completed_objectives: list[str]
    research_gaps: list[dict]

    thesis_ledger: list[dict]
    claim_ledger: list[dict]
    evidence_ledger: list[dict]
    assumption_ledger: list[dict]
    metric_store: dict

    historical_financials: dict
    operating_kpis: dict
    forecast_model: dict
    valuation_model: dict
    scenario_analysis: dict

    risk_map: list[dict]
    catalyst_calendar: list[dict]

    section_drafts: dict
    review_findings: list[dict]
    ic_review: dict
    final_report: str

    data_quality_flags: list[dict]
    compliance_flags: list[dict]

    next_route: str
```

---

# 18. 研究计划应该长什么样？

`generate_research_plan` 的输出不要只是章节列表，而应该是 thesis-driven。

例如：

```python
{
    "core_questions": [
        {
            "id": "Q1",
            "question": "Is the market underestimating cloud revenue growth?",
            "priority": "high",
            "linked_sections": ["investment_thesis", "business_model", "forecast"],
            "required_skills": [
                "broker_consensus_mining",
                "operating_kpi_extraction",
                "variant_view_discovery"
            ],
            "success_criteria": [
                "consensus revenue estimates collected",
                "management guidance extracted",
                "at least 2 pieces of evidence supporting or refuting upside"
            ]
        },
        {
            "id": "Q2",
            "question": "Is margin expansion sustainable?",
            "priority": "high",
            "linked_sections": ["historical_financials", "forecast", "valuation"],
            "required_skills": [
                "historical_financial_analysis",
                "business_model_analysis",
                "risk_counterthesis"
            ]
        }
    ]
}
```

这样系统会围绕研究问题，而不是围绕模板填空。

---

# 19. 专业深度来自哪里？

如果你要让研报“有深度”，至少要强制系统完成 7 件事。

---

## 19.1 必须有 Consensus Map

```text
市场怎么看？
```

包括：

- broker rating；
- target price；
- EPS；
- revenue；
- margin；
- bull case；
- bear case；
- key debates。

---

## 19.2 必须有 Variant View

```text
我们和市场哪里不一样？
```

如果没有 variant view，报告就只是 facts summary。

---

## 19.3 必须有 Driver Tree

```text
收入和利润由什么驱动？
```

例如：

```text
Revenue = Volume × ASP × Mix
Gross Profit = Revenue × Gross Margin
EBIT = Gross Profit - Opex
EPS = Net Income / Diluted Shares
Target Price = EPS × Target P/E
```

---

## 19.4 必须有 Assumption Bridge

```text
假设如何从证据走到预测？
```

例如：

```text
Backlog + management guidance + industry growth
→ FY2026 revenue growth assumption
→ EPS forecast
→ target price
```

---

## 19.5 必须有 Risk-to-Thesis Mapping

不是泛泛写风险，而是：

```text
哪个风险会推翻哪个 thesis？
```

---

## 19.6 必须有 Sensitivity

专业投资判断一定要知道：

```text
如果关键假设错了，target price 变多少？
```

---

## 19.7 必须有 Evidence Traceability

每个关键判断都要能追溯来源。

---

# 20. 如何给 Agent 加 Skills？

未来加 skill 的流程建议标准化。

---

## 20.1 每个 Skill 一个目录

```text
skills/
  broker_consensus_mining/
    manifest.yaml
    skill.py
    prompts.py
    schemas.py
    tests.py
  valuation/
    manifest.yaml
    skill.py
    schemas.py
    calculators.py
    tests.py
  risk_counterthesis/
    manifest.yaml
    skill.py
    prompts.py
    schemas.py
    tests.py
```

---

## 20.2 Skill Manifest 示例

```yaml
name: risk_counterthesis
description: Identify risks and counter-evidence for investment thesis.
version: 1.0.0

triggers:
  - risk section needed
  - IC review asks for counter-thesis
  - core thesis confidence below threshold

inputs:
  - thesis_ledger
  - claim_ledger
  - evidence_ledger
  - forecast_model
  - valuation_model

outputs:
  - risk_to_thesis_mapping
  - counter_evidence
  - downside_scenario
  - leading_indicators

allowed_tools:
  - search_filings
  - search_transcripts
  - search_news
  - retrieve_claims
  - retrieve_evidence
  - store_claim

quality_gates:
  - each core thesis must have at least one mapped risk
  - each high-impact risk must have evidence
  - generic risk language is not allowed
```

---

## 20.3 Skill Test

每个 skill 应该有测试：

- schema 是否合格；
- 是否引用 evidence；
- 是否调用了允许工具；
- 是否没有 hallucinated source；
- 输出是否可被 state 接收；
- 是否满足 minimum evidence count。

---

# 21. Human-in-the-loop 应该放在哪里？

专业分析师工具不应该假装完全自动化。建议在人类最有价值的地方插入。

---

## 21.1 Research Plan Approval

Agent 生成研究计划后，让分析师确认：

```text
这些研究问题是不是对？
```

---

## 21.2 Forecast Assumption Approval

在生成 forecast 前，让分析师确认关键假设：

- revenue growth；
- margin；
- capex；
- WACC；
- terminal growth；
- target multiple。

---

## 21.3 IC Review Override

如果系统自己审查失败，可以请求人类：

```text
是否接受这个风险？
是否继续研究？
是否调整 rating？
```

---

# 22. 推荐的权限设计

不同 agent/skill 对 tools 的权限不同。

例如：

```python
TOOL_PERMISSIONS = {
    "BrokerConsensusMiningSkill": [
        "search_broker_reports",
        "parse_pdf",
        "extract_tables",
        "store_evidence"
    ],
    "ForecastAssumptionSkill": [
        "get_financial_statements",
        "retrieve_evidence",
        "calculate_cagr",
        "store_assumption"
    ],
    "ValuationSkill": [
        "get_current_price",
        "get_peer_multiples",
        "calculate_dcf",
        "calculate_sensitivity_table"
    ],
    "SectionWritingSkill": [
        "retrieve_claims",
        "retrieve_evidence"
    ]
}
```

这可以减少 agent 胡乱调用工具。

---

# 23. 质量评分系统

你可以给每个章节和整篇报告打分。

---

## 23.1 Section Quality Score

```python
{
    "section": "industry_and_competition",
    "evidence_score": 0.82,
    "specificity_score": 0.76,
    "freshness_score": 0.91,
    "contradiction_score": 0.65,
    "numerical_consistency_score": 0.88,
    "overall_score": 0.80
}
```

---

## 23.2 报告必须过的门槛

```python
BLOCKING_RULES = [
    "rating_missing",
    "target_price_missing",
    "current_price_missing",
    "rating_upside_mismatch",
    "no_variant_view",
    "no_consensus_comparison",
    "valuation_not_reproducible",
    "forecast_assumptions_without_evidence",
    "core_thesis_without_counter_evidence",
    "hallucinated_citation",
    "stale_market_price",
]
```

---

# 24. 你当前代码具体怎么改？

你现在的节点很多：

```python
generate_hypotheses
virtual_evaluate
allocate_budget
retrieve_evidence
extract_facts
verify_claims
evaluate_stop_condition
write_section
review_section
...
```

建议不要全删，而是重构成三层。

---

## 24.1 保留 Workflow 节点

保留：

```python
initialize_state
load_report_template
discover_consensus
find_expectation_gaps
business_driver_decomp
financial_forecast
valuation
investment_committee_review
assemble_report
chart_generation
markdown_memory_export
```

但要调整顺序。

---

## 24.2 合并开放研究节点

把这些：

```python
generate_hypotheses
virtual_evaluate
allocate_budget
retrieve_evidence
extract_facts
verify_claims
evaluate_stop_condition
```

封装成：

```python
autonomous_research
```

内部由 Lead Analyst Agent 调 skill 和 tools。

外部 workflow 只关心：

```python
autonomous_research 是否完成？
是否需要更多研究？
是否要进入财务模型？
是否要 human review？
```

---

## 24.3 写作不要太早

把：

```python
write_investment_focus
```

放到：

```text
valuation
→ risk
→ IC review
```

之后。

---

# 25. 一个新的代码骨架

大概可以这样组织。

```python
class EquityResearchSystem:
    def __init__(self, deps):
        self.tools = ToolRegistry(deps)
        self.skills = SkillRegistry()
        self.lead_agent = LeadAnalystAgent(
            skill_registry=self.skills,
            tool_registry=self.tools,
        )

    def setup_graph(self):
        g = StateGraph(EquityResearchState)

        g.add_node("initialize_state", create_initialize_state())
        g.add_node("load_report_template", create_load_report_template())
        g.add_node("define_research_mandate", create_define_research_mandate())
        g.add_node("ingest_documents", create_ingest_documents())
        g.add_node("build_source_index", create_build_source_index())

        g.add_node("extract_broker_views", create_extract_broker_views())
        g.add_node("discover_consensus", create_discover_consensus())
        g.add_node("find_expectation_gaps", create_find_expectation_gaps())
        g.add_node("generate_research_plan", create_generate_research_plan())

        g.add_node("autonomous_research", self.lead_agent.autonomous_research_node)

        g.add_node("historical_financials", create_historical_financials())
        g.add_node("operating_kpi_extraction", create_operating_kpi_extraction())
        g.add_node("forecast_assumptions", create_forecast_assumptions())
        g.add_node("financial_forecast", create_financial_forecast())
        g.add_node("forecast_consistency_check", create_forecast_consistency_check())

        g.add_node("valuation", create_valuation_engine())
        g.add_node("scenario_sensitivity", create_scenario_sensitivity())
        g.add_node("rating_target_price_check", create_rating_target_price_check())

        g.add_node("risk_to_thesis_mapping", create_risk_to_thesis_mapping())
        g.add_node("catalyst_monitor", create_catalyst_monitor())

        g.add_node("investment_committee_review", create_investment_committee_review())
        g.add_node("write_investment_focus", create_write_investment_focus())
        g.add_node("write_remaining_sections", create_write_remaining_sections())

        g.add_node("plan_tables_and_charts", create_plan_tables_and_charts())
        g.add_node("chart_generation", create_chart_generation())
        g.add_node("assemble_report", create_assemble_report())
        g.add_node("final_consistency_check", create_final_consistency_check())
        g.add_node("compliance_check", create_compliance_check())
        g.add_node("markdown_memory_export", create_markdown_memory_export())

        return g
```

---

# 26. 推荐路线图

## P0：先把系统从“写作 workflow”升级成“研究 workflow”

优先做：

1. `Research Mandate`
2. `Source Index`
3. `Evidence Ledger`
4. `Claim Ledger`
5. `Assumption Ledger`
6. `Autonomous Research Node`
7. `Skill Registry`
8. `Tool Registry`
9. `Final Consistency Check`

---

## P1：把专业深度做出来

加入：

1. `BrokerConsensusMiningSkill`
2. `VariantViewDiscoverySkill`
3. `ConsensusBridge`
4. `RiskCounterThesisSkill`
5. `ForecastAssumptionSkill`
6. `ValuationSkill`
7. `ScenarioSensitivitySkill`

---

## P2：提升产品体验

加入：

1. human approval；
2. chart planner；
3. source reliability scoring；
4. stale data detection；
5. section quality score；
6. report diff；
7. broker view comparison dashboard；
8. analyst editable assumptions；
9. export to Markdown / Word / Excel / PowerPoint。

---

# 27. 最重要的设计原则

最后总结一下：

## 原则一：Workflow 管顺序，Agent 管探索

不要让 agent 自由决定整个报告流程；但也不要把每个研究动作写死。

---

## 原则二：LLM 负责推理，工具负责事实和计算

尤其是 target price、EPS、DCF、multiples，必须由工具算。

---

## 原则三：每个结论都要有证据链

没有 evidence 的 claim 不进报告。

---

## 原则四：每个核心 thesis 都要有反证

没有 counter-thesis 的报告不专业。

---

## 原则五：先研究，后写作

不要让系统一边找一点资料一边写最终稿。  
正确顺序是：

```text
research → model → valuation → risk → IC review → write executive summary
```

---

## 原则六：Skills 是你未来扩展系统的核心

以后你想加能力，不要改整个 graph。  
只需要：

```text
新增 Skill → 注册 Skill → 定义触发条件 → 定义 tools 权限 → 定义输出 schema → 加测试
```

---

# 最终建议

你应该把当前系统改造成：

```text
Workflow Spine + Lead Analyst Agent + Skill Registry + Tool Layer + Research Ledgers + Quality Gates
```

其中：

- **Workflow** 保证流程专业、可控、可审计；
- **Agent** 负责开放式研究和判断；
- **Skills** 负责可复用的专业研究能力；
- **Tools** 负责数据、检索、计算和制图；
- **Ledgers** 保证证据、判断和假设可追溯；
- **Quality Gates** 保证报告不会“看起来专业但其实没依据”。

这样你的产品才会从“自动写研报”升级成真正有价值的：

> **Equity Research Copilot for professional analysts.**

