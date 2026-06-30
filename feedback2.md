可以。基于你给的运行时说明，我基本可以定位出当前 Assumption 输出“像扩充版 Consensus Report”的几个核心原因。问题不是单一 prompt 写得不够好，而是 **Skill 加载、Schema 设计、Planner 维度、Synthesizer 合并逻辑、Reflector 评分标准** 五个地方共同把 Assumption Task 拉回了 consensus summarization。

下面按严重程度诊断。

---

# 总体诊断

当前架构设计方向是对的：

```text
Consensus Subgraph：市场现在相信什么？
Assumption Subgraph：这些市场观点成立需要哪些隐含前提？
```

但当前 Assumption Subgraph 的运行时实现里，有几个机制会系统性导致它输出：

```text
“市场共识的再总结 + 一些研究方向”
```

而不是：

```text
“隐含假设图谱 + 证据支持/反驳 + 可证伪测试 + 后续研究计划”
```

我认为最关键的问题有 7 个。

---

# 1. 最大问题：Assumption 专用 skill 可能没有被加载

你文档里这句非常关键：

> `market_assumption_decomposition.md`（非 `*.skill.md`），可能未进入运行时目录扫描；若 fallback 失败，将退回到目录中第一个可用 skill（通常为 `broker_consensus_mining`）。

这是一个高优先级 bug。

如果 `market_assumption_decomposition` 没有被扫描到，Assumption Subgraph 实际上很可能加载的是：

```text
broker_consensus_mining
```

而这个 skill 的任务是：

```text
Rebuild the market consensus framework via search and structured extraction.
```

它的 Prompt Template 是：

```text
You are a sell-side consensus analyst...
Rebuild the market consensus framework from public evidence...
```

它的 Query Guidance 是：

```text
- analyst consensus revenue EPS estimates
- key metrics analysts watch
- forward PE EV EBITDA
- bull bear investment thesis
- estimate revision guidance change
```

这会直接把 Assumption Task 变成第二轮 Consensus Task。

所以你看到的输出：

- 重新描述 NVDA business model；
- 重新列 FY2026 revenue / EPS / FCF；
- 重新列 analyst ratings 和 price targets；
- 重新总结 bull/bear debate；
- 重新讲 valuation multiple；

很可能不是 LLM 偶然跑偏，而是 skill 层面给了它错误身份。

## 建议修复

### 立即修复

把：

```text
skills/definitions/market_assumption_decomposition.md
```

改名为：

```text
skills/definitions/market_assumption_decomposition.skill.md
```

并确认 skill registry 能扫描到。

### 进一步修复

给 `assumption_subgraph` 单独配置 visibility，不要默认暴露所有 skill。

建议：

```python
assumption_subgraph:
  include_names:
    - market_assumption_decomposition
    - forecast_assumption_builder
    - risk_counterthesis
    - variant_view_discovery
    - valuation
  exclude_names:
    - broker_consensus_mining
```

或者至少不要让 `broker_consensus_mining` 成为 assumption fallback。

### 更强约束

Assumption Task 可以不让 LLM 自由选 skill，而是强制加载：

```text
market_assumption_decomposition
risk_counterthesis
```

因为这个任务边界很清晰，不一定需要 LLM 做 skill selection。

---

# 2. Assumption Schema 本身太像 Consensus Report

你当前的 `ConsensusAssumptions` 字段是：

```text
business_model
market_sentiment
key_metrics_watched
valuation_rationale
earnings_focus
recent_expectation_changes
benchmark_expectations
sellside_model_drivers
key_debates
stress_test_candidates
recommended_next_data
sources
```

这个 schema 最大的问题是：  
**它不是“假设 schema”，而是“研究备忘录章节 schema”。**

这些字段天然会诱导模型写：

```text
商业模式是什么？
市场情绪是什么？
市场看哪些 KPI？
估值逻辑是什么？
财报关注什么？
近期预期怎么变化？
```

这当然会变成扩充版 consensus。

真正的 Assumption Task 应该以“单条假设”为基本单元，而不是以 report section 为基本单元。

---

## 当前 schema 导致的具体问题

例如字段：

```text
business_model
```

模型很自然会写：

```text
NVIDIA designs and sells AI accelerators and full-stack data center infrastructure...
```

但真正的 assumption 应该是：

```text
The market is implicitly assuming NVIDIA can continue expanding content per AI cluster through rack-scale systems and networking attach.
```

再如字段：

```text
market_sentiment
```

模型自然会写：

```text
Public sell-side sentiment is strongly bullish...
```

但真正的 assumption 应该是：

```text
The market is implicitly assuming current bullish sentiment is supported by future estimate revisions rather than only multiple expansion.
```

所以当前输出不像 assumption，根本原因之一是 **数据结构不要求模型输出 assumption**。

---

## 建议改 Schema

建议把 `current_assumptions` 从 section-based 改为 item-based。

例如：

```json
{
  "assumption_map": [
    {
      "id": "A1",
      "statement": "The market is implicitly assuming hyperscaler AI capex remains elevated through CY2026-CY2027.",
      "category": "demand",
      "consensus_anchor": "Consensus expects sustained Data Center revenue growth and strong Blackwell ramp.",
      "model_drivers": [
        "Data Center revenue growth",
        "order backlog",
        "valuation multiple"
      ],
      "evidence_for": [],
      "evidence_against": [],
      "confidence": "medium",
      "controversy_level": "high",
      "model_sensitivity": "very_high",
      "time_to_resolution": "next_1_to_3_quarters",
      "leading_indicators": [],
      "falsification_tests": [],
      "recommended_next_checks": [],
      "source_doc_ids": []
    }
  ],
  "top_research_priorities": [],
  "open_questions": [],
  "watchlist": []
}
```

核心是每条都必须回答：

| 字段 | 目的 |
|---|---|
| `statement` | 市场隐含假设是什么 |
| `consensus_anchor` | 这个假设从哪条共识推导出来 |
| `model_drivers` | 它影响模型里的哪个变量 |
| `evidence_for` | 哪些证据支持 |
| `evidence_against` | 哪些证据挑战 |
| `controversy_level` | 市场分歧强不强 |
| `model_sensitivity` | 对估值敏感不敏感 |
| `falsification_tests` | 什么数据会推翻它 |
| `recommended_next_checks` | 后续该查什么 |

这才是 assumption engine。

---

# 3. Assumption Planner 的维度设计仍然是“研究报告维度”

当前 assumption planner 的 target dimensions 是：

```text
business_model
market_sentiment
key_metrics
valuation
earnings_focus
expectation_changes
benchmark_expectations
model_drivers
debates
stress_test
next_data
```

这些维度太像 general equity research outline，而不是 assumption decomposition outline。

其中尤其容易跑偏的是：

```text
business_model
market_sentiment
key_metrics
valuation
earnings_focus
expectation_changes
```

它们会让 Perplexity 搜到：

- company business overview；
- analyst ratings；
- price target；
- earnings preview；
- consensus estimate；
- valuation snapshot。

这些正是 consensus 内容。

---

## 建议改成真正的假设类型维度

对 NVDA 这类股票，Assumption Task 的维度应该更像（建议将NVDA这类的研究作为一个单独的skill.md，在研究NVDA时load进来。）：

```text
demand_assumptions
product_cycle_assumptions
margin_assumptions
competitive_assumptions
customer_capex_assumptions
supply_chain_assumptions
regulatory_geopolitical_assumptions
valuation_assumptions
estimate_revision_assumptions
variant_view_assumptions
falsification_tests
```

或者更通用一点：

```text
market_implied_demand
market_implied_margin
market_implied_growth_duration
market_implied_competition
market_implied_capital_cycle
market_implied_regulatory_risk
market_implied_valuation
evidence_against_consensus
falsification_signals
next_data_to_watch
```

这些维度会迫使模型问：

```text
市场隐含了什么需求假设？
市场隐含了什么利润率假设？
市场隐含了什么竞争格局假设？
市场隐含了多长的增长持续期？
哪些数据可以证伪这些假设？
```

而不是问：

```text
市场现在怎么看？
分析师看哪些 KPI？
估值倍数是多少？
```

---

# 4. Synthesizer Prompt 没有强制“从共识推导假设”

当前 Assumption Synthesizer Prompt 是：

```text
Update the assumption research view for {ticker} using new search evidence.

Market consensus (read-only context):
{consensus_view}

Current assumption view:
{format_assumption_view(view)}

New search evidence:
{evidence_text}

Merge incrementally. Populate current_assumptions from evidence only.
Add research_suggestions...
Label unverified claims [UNVERIFIED]. Keep conflicts with [CON].
```

这里有两个问题。

---

## 问题 1：“Populate current_assumptions from evidence only” 会导致证据摘要，而不是假设推导

隐含假设不一定直接写在证据里。  
它通常需要从共识中逆向推导。

例如 consensus 是：

```text
FY2026 Data Center revenue expected around $181.9B.
```

Assumption 应该推导出：

```text
The market is implicitly assuming hyperscaler AI infrastructure demand remains elevated and NVDA retains dominant accelerator share.
```

但如果要求：

```text
Populate from evidence only
```

模型会更倾向于写：

```text
Data Center revenue consensus is $181.9B.
```

这就回到了 consensus。

### 建议改法

改成：

```text
Infer the implicit assumptions that must be true for the consensus view to hold.
Use consensus_view only as an anchor.
Use new evidence to support, challenge, or refine each inferred assumption.
Do not restate consensus facts unless they are used as a one-line anchor.
```

---

## 问题 2：没有禁止复制 consensus 内容

你现在说了：

```text
Market consensus read-only context
```

但没有说：

```text
Do not summarize or rewrite the consensus view.
```

LLM 看到大段 consensus，自然会复述。

### 建议加硬约束

在 Assumption Synthesizer Prompt 里加：

```text
Do NOT produce a consensus summary.
Do NOT restate business model, market sentiment, KPI list, valuation multiples, or recent estimate changes unless converting them into an explicit implicit assumption.

Every assumption must be written in the form:
"The market is implicitly assuming that..."

Each assumption must include:
- consensus_anchor
- why_it_matters_to_model
- evidence_for
- evidence_against
- falsification_tests
- next_data_to_watch
```

这类格式约束非常重要。

---

# 5. `[CON]` 和 `[UNVERIFIED]` 策略导致文本堆叠、重复和污染

当前两个 subgraph 都有类似逻辑：

```text
If conflict, keep both views and label [CON].
Label unverified claims [UNVERIFIED].
Merge incrementally — do not erase existing content.
```

这会导致几个现象：

1. 同一观点多次被 append；
2. `[CON]` 被当成自然语言前缀不断拼接；
3. `[UNVERIFIED]` 混在字段里；
4. LLM 不会真正 resolve conflict，只会堆叠；
5. 最终 structured view 变成累积笔记，而不是干净的研究产物。

你给的 assumption 输出里就有明显痕迹：

```text
[CON] NVIDIA designs and sells...
[CON] NVIDIA designs and sells...
```

以及：

```text
FY2026 revenue ~$200B-$210B [UNVERIFIED]
```

这些应该是结构化 metadata，不应该混进主文本。

---

## 建议改法

### 把 `[UNVERIFIED]` 改成字段

不要这样：

```text
"FY2026 revenue ~$200B-$210B [UNVERIFIED]"
```

改成：

```json
{
  "claim": "FY2026 revenue consensus is around $200B-$210B",
  "verification_status": "unverified",
  "confidence": "low",
  "source_quality": "aggregator"
}
```

### 把 `[CON]` 改成 conflict object

不要这样：

```text
[CON] Data Center revenue revised down...
[CON] Management says demand is strong...
```

改成：

```json
{
  "conflict": {
    "claim_a": "Data Center revenue consensus revised down from $188.6B to $181.9B",
    "claim_b": "Management commentary indicates continued strong Blackwell demand",
    "interpretation": "Near-term demand remains strong, but consensus has become more cautious on Data Center margin/revenue.",
    "resolution_status": "unresolved",
    "next_check": "Compare provider-specific estimate revisions after next earnings."
  }
}
```

---

# 6. Merge 逻辑缺少语义去重

你的输出里有大量重复：

```text
Track Blackwell ramp and margin bridge through upcoming quarters
Track Blackwell ramp and gross margin bridge through upcoming quarters
```

还有：

```text
Quantify networking attach and full-system revenue contribution
Refine networking monetization model for GB200/NVL72
Quantify NVLink and Spectrum-X run-rates and attach rates
```

这说明 `merge_view_fn` 很可能是 append-heavy，没有做 semantic dedupe。

---

## 建议加 dedupe 规则

对 `research_suggestions`、`research_directions`、`key_debates`、`stress_test_candidates` 这类 list 字段，建议做：

### 1. Canonical key

例如将 direction 标准化：

```text
Track Blackwell ramp and margin bridge
Track Blackwell ramp and gross margin bridge
```

统一为：

```text
blackwell_ramp_margin_bridge
```

### 2. 相似度去重

可以用 embedding similarity 或简单 token overlap：

```python
if cosine_similarity(new_item, existing_item) > 0.85:
    merge instead of append
```

### 3. 优先级合并

重复方向合并时：

```text
priority = min(existing.priority, new.priority)
rationale = concise merged rationale
sources = union(sources)
```

---

# 7. Reflector 评分标准太宽，导致错误产物也能高分退出

Assumption Reflector 当前 prompt 是：

```text
Score each assumption dimension as empty, partial, sufficient, or strong.
Provide overall_score.
List critical_gaps as dimension names still weak.
```

它评估的是：

```text
business_model 有没有？
market_sentiment 有没有？
valuation 有没有？
debates 有没有？
stress_test 有没有？
next_data 有没有？
```

只要这些 section 被填满，它就会给高分。

这解释了为什么当前 assumption 输出 coverage_score 能到：

```json
0.92
```

但实际质量仍然不像 assumption。

因为 reflector 没有评估：

- 是否真的提取了隐含假设；
- 是否每条假设可证伪；
- 是否绑定模型变量；
- 是否区分 evidence_for / evidence_against；
- 是否识别市场分歧；
- 是否有 next data；
- 是否去重；
- 是否避免复述 consensus。

---

## 建议改 Reflector 维度

把 assumption coverage 改成质量维度，而不是主题维度。

例如：

```text
assumption_identification
consensus_to_assumption_linkage
model_driver_linkage
evidence_balance
falsifiability
variant_view_detection
research_actionability
deduplication_quality
source_quality
```

新的 reflector prompt 可以要求：

```text
Evaluate whether the output is a true assumption map, not a consensus summary.

Score the following:
1. Are implicit assumptions explicitly stated?
2. Is each assumption linked to a consensus anchor?
3. Is each assumption linked to model drivers?
4. Does each assumption include evidence for and against?
5. Are falsification tests provided?
6. Are next data checks actionable?
7. Is there excessive repetition of consensus facts?
8. Are duplicate suggestions merged?
```

并加入硬性 critical gap：

```text
If more than 30% of the output restates consensus facts, mark critical_gaps += ["over_summarizes_consensus"].
If fewer than 3 assumptions have falsification tests, mark critical_gaps += ["missing_falsification_tests"].
If assumptions are not linked to model drivers, mark critical_gaps += ["missing_model_linkage"].
```

---

# 8. 继承 consensus evidence/search_memory 有副作用

Assumption seed 当前继承：

```text
search_memory = consensus_search_memory
evidence_buffer = consensus_evidence_buffer
parent_context = consensus_view + consensus_report
```

这个设计有优点：避免重复搜索。

但它也有副作用：

1. Planner 看到 prior search memory，可能被 consensus query 影响；
2. Finalizer 看到 search memory summary，可能继续引用 consensus evidence；
3. Assumption evidence_buffer 混入 consensus evidence，source_doc_ids 边界不清；
4. 如果 format 函数或 trace 使用 evidence_buffer，模型会更容易复述 consensus；
5. 搜索去重可能阻止它重新验证关键 assumption。

---

## 建议调整

### 保留 search_memory 仅用于 dedupe

可以继承 consensus `search_memory`，但只暴露为：

```text
Already searched topics for deduplication only.
Do not summarize these records.
```

### 不建议把 consensus_evidence_buffer 直接作为 assumption evidence_buffer

更好的做法：

```text
parent_context.consensus_view = consensus anchor
parent_context.consensus_report = optional excerpt
search_memory = consensus_search_memory for dedupe only
evidence_buffer = empty for assumption-specific evidence
pending_evidence = new assumption search evidence only
```

这样 assumption 的 evidence 更干净。

### 给 source_doc_ids 分层

例如：

```json
"source_doc_ids": {
  "consensus_anchor_docs": [],
  "assumption_validation_docs": []
}
```

---

# 9. Consensus Subgraph 本身也有一些会传导到 Assumption 的问题

虽然你主要问 assumption，但 consensus 的质量会直接影响 assumption。

## 9.1 Consensus 缺少 source quality

Skill constraint 说：

```text
Attribute source reliability for each dimension
```

但 schema 里没有强制 source reliability 字段。

所以最后 sources 里混在一起：

- Yahoo Finance；
- MarketBeat；
- Reddit；
- YouTube；
- Seeking Alpha；
- SimplyWallSt；
- S&P Global；
- company IR。

这些不应该同权。

建议每个 source 加：

```json
{
  "url": "...",
  "source_type": "primary / institutional / aggregator / media / social",
  "reliability": "high / medium / low",
  "used_for": "estimate / sentiment / narrative / valuation"
}
```

并限制：

```text
Do not use Reddit/YouTube/social sources as core estimate evidence.
```

---

## 9.2 Consensus 数字口径不够严格

你之前输出里有：

```text
FY2026 revenue ~$200B-$210B
Q1 FY2027 revenue ~$82B
Q2 FY2027 guidance ~$89B-$92B
```

这类数据必须严格标注：

```text
fiscal year
calendar year
quarter
period end
GAAP / non-GAAP
actual / guidance / consensus / third-party estimate
source date
```

否则 assumption 里的 model driver 会建立在混乱的共识数字上。

建议 quantitative schema 里加：

```json
{
  "metric": "Revenue",
  "period": "FY2026",
  "period_end": "Jan 2026",
  "estimate_type": "consensus",
  "basis": "non-GAAP / GAAP / unknown",
  "low": "",
  "median": "",
  "high": "",
  "source": "",
  "source_quality": "",
  "as_of": ""
}
```

---

# 10. 我认为当前问题的根因排序

按重要性排序：

| 优先级 | 问题 | 影响 |
|---|---|---|
| P0 | `market_assumption_decomposition` 可能未被扫描，fallback 到 `broker_consensus_mining` | 直接把 assumption 变成 consensus |
| P0 | Assumption schema 是 section-based，不是 assumption-item-based | 输出形态天然像报告 |
| P1 | Planner 维度像 research memo，而不是 hidden assumptions | 搜索结果偏 consensus |
| P1 | Synthesizer 没有禁止复述 consensus，也没有强制 “market implicitly assumes...” | 任务边界不清 |
| P1 | Reflector 只评估主题覆盖，不评估假设质量 | 错误产物也能 0.92 高分退出 |
| P2 | `[CON]` / `[UNVERIFIED]` 以文本拼接形式进入结构化结果 | 输出脏、重复、难用 |
| P2 | merge 缺少 semantic dedupe | research suggestions 重复 |
| P2 | consensus source quality 和 period normalization 不足 | 传导到 assumption 的可靠性下降 |

---

# 11. 建议的最小改动方案

如果你不想大改 GenericResearchSubgraph，只想先快速改善，我建议做下面 5 个最小改动。

---

## 改动 1：修复 skill 文件和 visibility

```text
market_assumption_decomposition.md
→ market_assumption_decomposition.skill.md
```

并配置：

```text
assumption_subgraph include:
- market_assumption_decomposition
- risk_counterthesis
- variant_view_discovery
- forecast_assumption_builder

exclude:
- broker_consensus_mining
```

---

## 改动 2：修改 Assumption Synthesizer Prompt

加入硬约束：

```text
Do not summarize the consensus view.
Use the consensus view only to infer implicit assumptions.

Every assumption must be phrased as:
"The market is implicitly assuming that..."

For each assumption, include:
- consensus_anchor
- model_driver
- evidence_for
- evidence_against
- falsification_tests
- next_data_to_watch
- confidence
- controversy_level

If a claim is merely a consensus fact, do not include it unless it is converted into an implicit assumption.
```

---

## 改动 3：替换 Assumption 维度

从：

```text
business_model
market_sentiment
key_metrics
valuation
earnings_focus
expectation_changes
...
```

改为：

```text
demand_assumptions
product_ramp_assumptions
margin_assumptions
competition_assumptions
valuation_assumptions
regulatory_assumptions
estimate_revision_assumptions
falsification_tests
next_data_to_watch
```

---

## 改动 4：修改 Reflector Prompt

加入：

```text
Penalize outputs that restate consensus rather than infer assumptions.
Mark critical gap if assumptions lack falsification tests.
Mark critical gap if assumptions are not linked to model drivers.
Mark critical gap if there is excessive duplication.
```

并把 coverage dimensions 改为：

```text
assumption_identification
model_linkage
evidence_balance
falsifiability
research_actionability
deduplication_quality
source_quality
```

---

## 改动 5：对 research_suggestions 做去重

合并类似：

```text
Track Blackwell ramp and margin bridge
Track Blackwell ramp and gross margin bridge
```

输出一个 canonical direction：

```json
{
  "direction": "Blackwell ramp and gross margin bridge",
  "priority": 1,
  "related_assumptions": ["A2"],
  "next_checks": [
    "next-quarter Blackwell shipment commentary",
    "non-GAAP gross margin guidance",
    "product mix/ramp cost disclosure"
  ]
}
```

---

# 12. 更理想的 Assumption 输出应长什么样

以 NVDA 为例，最终不应该是：

```text
NVIDIA sells AI accelerators...
Market sentiment is positive...
FY2026 revenue consensus is...
```

而应该是：

```json
{
  "assumption_map": [
    {
      "id": "A1",
      "statement": "The market is implicitly assuming hyperscaler AI capex remains elevated through CY2026-CY2027.",
      "category": "demand",
      "consensus_anchor": "Consensus expects sustained Data Center growth and strong Blackwell demand.",
      "model_drivers": [
        "Data Center revenue growth",
        "order backlog",
        "valuation multiple"
      ],
      "evidence_for": [
        "Recent guidance and sell-side revisions imply continued hyperscaler demand."
      ],
      "evidence_against": [
        "Official hyperscaler capex guidance may not fully support top-down AI infrastructure claims.",
        "ROI and capex fatigue concerns are rising."
      ],
      "controversy_level": "high",
      "model_sensitivity": "very_high",
      "falsification_tests": [
        "MSFT/AMZN/GOOG/META capex guidance slows materially.",
        "FY2027 Data Center revenue consensus is revised down by more than 10%."
      ],
      "next_data_to_watch": [
        "Hyperscaler quarterly capex disclosures",
        "AI server backlog",
        "CoreWeave/Oracle/sovereign AI demand commentary"
      ]
    },
    {
      "id": "A2",
      "statement": "The market is implicitly assuming Blackwell ramp execution remains smooth and does not materially dilute gross margin.",
      "category": "product_cycle_margin",
      "consensus_anchor": "Consensus expects Blackwell ramp and gross margin in the mid-70%s.",
      "model_drivers": [
        "Revenue growth",
        "gross margin",
        "EPS"
      ],
      "controversy_level": "medium_high",
      "model_sensitivity": "high",
      "falsification_tests": [
        "Non-GAAP gross margin guidance falls below 72%-73%.",
        "Management cites Blackwell ramp complexity or supply bottlenecks.",
        "Sell-side FY2027 gross margin estimates are cut by more than 150 bps."
      ]
    }
  ],
  "top_research_priorities": [
    "Hyperscaler capex reality check",
    "Blackwell ramp and margin bridge",
    "Networking attach and rack-scale monetization",
    "Custom ASIC and inference competition",
    "Valuation under growth normalization"
  ]
}
```

这种输出才是真正能喂给后续 `research_loop` 和建模模块的。

---

# 最终判断

你当前的 Assumption Task 的确存在你说的问题：

> 它不像一个真正的 Assumption Task，更像一个扩充版 Consensus Report。

主要原因不是 LLM 能力问题，而是运行时配置和 schema/prompt 设计共同导致的：

1. assumption 专用 skill 可能没加载；
2. fallback 可能加载了 consensus skill；
3. schema 是报告章节式，不是假设列表式；
4. planner 维度偏 consensus/research memo；
5. synthesizer 没强制“共识 → 隐含假设”的转换；
6. reflector 只看覆盖率，不看假设质量；
7. merge 逻辑导致重复堆叠。

如果优先修三个地方，我建议顺序是：

```text
1. 修复 assumption skill discovery 和 visibility
2. 重构 AssumptionView schema 为 assumption_map
3. 改 reflector 评分标准，从 topical coverage 改为 assumption quality
```

这三项改完，Assumption Task 的输出形态会明显从“共识扩写”转向“假设图谱 + 研究路线”。