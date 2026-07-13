# RiskMapping：风险映射与催化剂日历

> 语言：[中文](risk-mapping.md) · [English](../EQUITY_RESEARCH.md)  
> 模块路径：`tradingagents/equity_research/agents/risk_mapping.py`、`workflow_agents.py`  
> 相关文档：[EQUITY_RESEARCH.md](../EQUITY_RESEARCH.md) · [Skills & Tools](../equity_research/skills-and-tools.md)

本文档描述 `risk_mapping` 节点在研究流水线中的定位、两个子工作流（风险→论点映射和催化剂日历）的算法。

---

## 1. 定位

`risk_mapping` 位于 `branch_merge` 之后、`investment_committee_review` 之前：

```text
… → branch_merge
    → risk_mapping              # ← 此处
    → investment_committee_review
    → …
```

目标：将研究发现的风险与已有论点建立映射关系，同时生成催化剂事件日历，为 IC 审阅提供完整的风险/催化剂上下文。

---

## 2. 子工作流

### 2.1 Risk-to-Thesis Mapping

实现于 `create_risk_to_thesis_mapping()`（`workflow_agents.py`）。两种模式：

**无 `risk_counterthesis` Skill 时（回退路径）**：
从 `expectation_gaps` 前 5 条直接构造简单风险映射：

| 字段 | 来源 |
|------|------|
| `risk_id` | UUID |
| `description` | gap.description |
| `thesis_link` | gap.alpha_source |

**有 `risk_counterthesis` Skill 时（完整路径）**：
通过 `SkillRegistry` + `ToolRegistry.for_skill()` 调用 skill handler：

```python
skill = registry.get("risk_counterthesis")
tools = ToolRegistry(deps).for_skill(skill.manifest.allowed_tools)
output = skill.run(SkillInput(state_snapshot=state, objective="risk mapping"), tools)
```

输出更新：

| 状态字段 | 内容 |
|----------|------|
| `risk_map` | risk_counterthesis skill 产出的结构化风险评估列表 |
| `claims` | 原有 claims + skill 新产生的 claims（含证据链接） |

### 2.2 Catalyst Monitor

实现于 `create_catalyst_monitor()`（`workflow_agents.py`）：

从 `expectation_gaps` 提取中期催化剂，并自动添加"下次财报发布"作为近期催化剂：

| 字段 | 值 |
|------|-----|
| `catalyst_id` | UUID |
| `description` | expectation_gap.description |
| `timeframe` | `"medium_term"` |
| `thesis_link` | gap.alpha_source |

额外一条固定催化剂：

| 字段 | 值 |
|------|-----|
| `description` | "Next earnings release" |
| `timeframe` | `"near_term"` |
| `thesis_link` | "earnings validation" |

### 2.3 Ledger 同步

完成后调用 `sync_ledgers_from_legacy()` 确保新旧 state 格式一致，然后写入 `deps.trace()`。

---

## 3. State 输入/输出

| 输入字段 | 必须 | 说明 |
|----------|------|------|
| `expectation_gaps` | ✓ | consensus gap finder 产出 |
| `research_graph` | 否 | 论点 DAG（供 risk_counterthesis skill 参考） |
| `claims` | 否 | 已有主张（用于追加而非覆盖） |

| 输出字段 | 说明 |
|----------|------|
| `risk_map` | 风险→论点映射列表 |
| `claims` | 更新后的主张列表 |
| `catalyst_calendar` | 催化剂事件日历 |
| `last_updated` | ISO 8601 时间戳 |

---

## 4. 源码索引

| 文件 | 职责 |
|------|------|
| `agents/risk_mapping.py` | 主入口 (`create_risk_mapping`) |
| `agents/workflow_agents.py` | `create_risk_to_thesis_mapping`, `create_catalyst_monitor` |
| `skills/handlers/impl.py` | `risk_counterthesis` skill handler |
| `skills/definitions/` | `risk_counterthesis.skill.md` |
