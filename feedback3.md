# Equity Research Agent Evaluation Framework Requirements

## 1. Objective

建立一套可重复执行、可持续集成（CI）、可版本比较（Experiment Tracking）的 Evaluation Framework，用于评估 Equity Research Agent 的质量。

评估体系覆盖三个核心维度：

1. **End-to-End Quality（最终结果质量）**
2. **Trajectory Quality（执行轨迹质量）**
3. **Faithfulness（事实忠实度）**

所有评估应支持：

* 本地运行
* CI/CD 自动运行
* LangSmith Trace 集成
* LangSmith Experiment 比较
* 后续扩展新的 Evaluator

---

# 2. Scope

评估对象包括：

* EquityResearchGraph
* GenericResearchSubgraph
* Consensus Generator
* Planner
* Research Loop
* Valuation Pipeline

不包括：

* 单独 Tool 的功能测试
* LLM Provider Benchmark
* Latency Benchmark
* Infrastructure Stress Test

这些属于独立测试体系。

---

# 3. Evaluation Architecture

整体架构：

```text
EquityResearchGraph
         │
         ▼
     LangSmith Trace
         │
         ▼
 ┌────────────────────┐
 │ Evaluation Runner  │
 └────────────────────┘
         │
         ▼
 ┌────────┬────────┬────────┐
 │End2End │Trajectory│Faithful│
 └────────┴────────┴────────┘
         │
         ▼
      Scores
         │
         ▼
 LangSmith Experiment
```

---

# 4. Required Upstream Dependencies

## 4.1 LangSmith Tracing

所有 Agent Run 必须开启 Trace。

### Environment Variables

```bash
LANGSMITH_TRACING=true

LANGSMITH_API_KEY=...

LANGSMITH_PROJECT=equity-research
```

### Requirement

所有节点必须产生可追踪 Run：

* Planner
* Researcher
* Tool Calls
* Synthesizer
* Valuation

否则 Trajectory Evaluation 无法执行。

---

## 4.2 Structured Outputs

以下对象必须使用 Pydantic Schema。

### Required

```python
ConsensusView

SectionResearchPlan

CoverageEvaluation

FinalQA

ValuationOutput
```

### Requirement

所有最终状态必须包含：

```python
final_state = {
    "final_report": ...,
    "consensus_view": ...,
    "section_plans": ...,
    "valuation": ...
}
```

否则 End-to-End Evaluation 无法验证。

---

## 4.3 Evidence Tracking

Faithfulness Evaluation 的前提。

系统必须保存：

```python
evidence_ledger
```

示例：

```python
{
    "claim": "Revenue grew 18%",
    "source": "10-K",
    "citation": "...",
}
```

同时保留：

```python
search_memory
pending_evidence
tool_outputs
```

否则无法判断最终结论是否有依据。

---

# 5. Deliverables

项目中新增：

```text
evaluation/

├── evaluators/
│
│   ├── end_to_end.py
│   ├── trajectory.py
│   ├── faithfulness.py
│
├── datasets/
│
│   ├── nvda.json
│   ├── aapl.json
│   └── msft.json
│
├── prompts/
│
│   └── faithfulness_judge.txt
│
├── run_eval.py
│
└── README.md
```

---

# 6. End-to-End Evaluation

## Goal

验证 Agent 是否成功完成研究任务。

---

## Inputs

来自：

```python
final_state
```

---

## Checks

### Completion

检查：

```python
final_report
```

存在且非空。

---

### Required Sections

检查是否包含：

```text
Executive Summary

Business Overview

Industry Analysis

Financial Analysis

Valuation

Investment Thesis

Risk Factors

Rating
```

---

### Structured Output Validation

验证：

```python
ConsensusView

SectionResearchPlan

CoverageEvaluation
```

符合 Schema。

---

### Valuation Output

如果估值节点运行成功：

必须存在：

```python
target_price

rating
```

---

## Output

示例：

```json
{
  "completion": 1.0,
  "schema_valid": 1.0,
  "required_sections": 0.95,
  "valuation_present": 1.0
}
```

---

# 7. Trajectory Evaluation

## Goal

验证 Agent 是否以合理方式完成研究。

重点关注：

* 是否调用正确工具
* 是否进入死循环
* 是否超预算
* 是否遵守 Graph Workflow

---

## Inputs

LangSmith Trace

---

## Required Data

需要获取：

```python
trace_id

child_runs

tool_runs
```

---

## Checks

### Allowed Tools

允许：

```python
web_search

executor

store_evidence

valuation

financial_data
```

禁止：

```python
unknown_tool
```

---

### Tool Argument Validation

验证：

```python
ticker
query
date_range
```

是否合法。

---

### Loop Detection

检查：

```python
tool_call_count
```

例如：

```python
tool_call_count < 100
```

---

### Repeated Queries

检测：

```python
same_query_count
```

例如：

```text
NVDA earnings growth
NVDA earnings growth
NVDA earnings growth
```

超过阈值判定异常。

---

### Workflow Order

预期：

```text
Task Analysis

Planning

Research

Evidence Collection

Synthesis

Valuation

Final Report
```

出现明显逆序时降低评分。

---

## Output

```json
{
  "tool_validity": 1.0,
  "workflow_order": 0.9,
  "loop_score": 1.0,
  "budget_score": 0.8
}
```

---

# 8. Faithfulness Evaluation

## Goal

验证最终报告中的结论是否来源于真实证据。

这是整个体系中最重要的评估项。

---

## Inputs

需要聚合：

```python
tool_outputs

evidence_ledger

search_memory

final_report
```

---

## Required Upstream Change

必须提供：

```python
collect_trace_evidence(trace_id)
```

接口。

返回：

```python
{
    "tool_outputs": ...,
    "citations": ...,
    "evidence_ledger": ...
}
```

---

## Judge Model Evaluation

构造 Prompt：

```text
TOOL OUTPUTS

...

FINAL REPORT

...
```

要求 Judge：

### Step 1

抽取所有事实性陈述。

例如：

```text
Revenue grew 18%.

Gross margin expanded.

Target price is $210.
```

---

### Step 2

分类：

```text
SUPPORTED

UNSUPPORTED

CONTRADICTED
```

---

### Step 3

输出：

```json
{
  "supported": 15,
  "unsupported": 2,
  "contradicted": 0,
  "faithfulness": 0.88
}
```

---

## Failure Criteria

以下情况直接降低评分：

### Fabricated Numbers

例如：

```text
Revenue = $45B
```

但工具结果不存在。

---

### Missing Citations

报告引用数据但没有来源。

---

### Contradictory Statements

报告内容与：

```python
evidence_ledger
```

冲突。

---

# 9. LangSmith Integration Requirements

## Dataset

创建：

```text
equity-research-eval
```

数据格式：

```json
{
  "ticker": "NVDA",
  "reference_report": "...",
  "reference_rating": "Overweight"
}
```

---

## Experiment Naming

格式：

```text
equity-research-v1

equity-research-v2

equity-research-v3
```

---

## Required Metrics

LangSmith Dashboard 必须显示：

```text
completion_score

schema_score

trajectory_score

faithfulness_score

overall_score
```

---

# 10. CI/CD Requirements

新增：

```bash
pytest tests/equity_research
```

之外的：

```bash
python evaluation/run_eval.py
```

---

Nightly Job：

```bash
LANGSMITH_TRACING=true

python evaluation/run_eval.py
```

---

结果自动上传：

```text
LangSmith Experiments
```

---

# 11. Definition of Done

以下条件全部满足视为完成：

### Infrastructure

* LangSmith Trace 可正常生成
* Evaluation Runner 可运行

### End-to-End

* Schema Validation 完成
* Section Validation 完成
* Completion Validation 完成

### Trajectory

* Tool Audit 完成
* Loop Detection 完成
* Workflow Validation 完成

### Faithfulness

* Tool Output Aggregation 完成
* Evidence Aggregation 完成
* Judge Evaluation 完成

### LangSmith

* Dataset 创建完成
* Experiment 可自动生成
* Metrics 可在 Dashboard 展示

### CI

* Evaluation 可独立运行
* Nightly Benchmark 可执行

---

## 最终预期产出

系统应能够对任意一次 Equity Research Run 自动生成如下结果：

```json
{
  "ticker": "NVDA",
  "completion_score": 0.96,
  "schema_score": 1.0,
  "trajectory_score": 0.91,
  "faithfulness_score": 0.88,
  "overall_score": 0.92
}
```

并同步到 LangSmith，用于版本比较、回归检测和研究质量监控。
