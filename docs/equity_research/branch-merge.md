# BranchMerge：论点分支整合与最终投资主张

> 语言：[中文](branch-merge.md) · [English](../EQUITY_RESEARCH.md)  
> 模块路径：`tradingagents/equity_research/agents/branch_merge.py`  
> 相关文档：[EQUITY_RESEARCH.md](../EQUITY_RESEARCH.md) · [Research Loop](../equity_research/agent-loop-and-tasks.md)

本文档描述 `branch_merge` 节点在研究流水线中的定位、算法、输入输出以及它在 Ledger 系统中的影响。

---

## 1. 定位

`branch_merge` 是外层 LangGraph 流水线的**一次性步骤**，位于 `valuation_workflow` 之后、`risk_mapping` 之前：

```text
… → valuation_workflow
    → branch_merge              # ← 此处
    → risk_mapping
    → investment_committee_review
    → …
```

目标：在 research_loop 结束后（论点 DAG 探索完成），将多个高评分论点分支合并为一份统一的最终投资主张。

---

## 2. 算法流程

### 2.1 筛选候选节点

```python
scored = []
for node_id, raw in nodes.items():
    if raw.get("status") == "rejected":
        continue
    score = float(raw.get("real_score") or raw.get("virtual_score") or 0)
    scored.append((score, node_id, raw))
scored.sort(reverse=True)
best_nodes = [raw for _, _, raw in scored[:4]]
```

| 规则 | 说明 |
|------|------|
| 跳过 rejected | `status == "rejected"` 的节点不进入合并 |
| 分数源 | `real_score` > `virtual_score` > `0` |
| Top-N | 取前 4 个最高分节点 |

### 2.2 LLM 论点合并

调用 `thesis_merge_prompt`，向模型传入 `best_nodes` 的 thesis / evidence / score，要求输出：

| 字段 | 类型 | 说明 |
|------|------|------|
| `final_core_thesis` | string | 合并后的核心投资主张 |
| `variant_view` | list[str] | 支持/反对观点列表 |
| `supporting_points` | list[str] | 关键论据点 |
| `remaining_risks` | list[str] | 未解决的潜在风险 |

### 2.3 Ledger 写入

合并后自动创建两类更新：

1. **thesis_ledger** — 追加一条 `ThesisLedgerEntry`：
   - `statement`: `final_core_thesis`
   - `variant_view`: 前三条 `variant_view`
   - `confidence`: best_node 的分数

2. **claims** — 追加一条 `Claim`：
   - `claim_type`: `RECOMMENDATION`
   - `status`: `PARTIALLY_SUPPORTED`
   - `is_core_thesis`: `True`
   - `hypothesis_id`: `best_node_id` 或 `"merged"`

### 2.4 State 更新

```python
updates = {
    "thesis_ledger": updated_thesis_ledger,
    "claims": updated_claims,
    "cross_branch_discoveries": merge_result["supporting_points"][:10],
    "last_updated": datetime.utcnow().isoformat(),
}
```

---

## 3. 配置

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `top_n` | 4 | 合并的候选分支数 |
| `max_supporting_points` | 10 | cross_branch_discoveries 最大保留数 |

---

## 4. 观测性

通过 `deps.trace(state, "branch_merge", {...})` 记录：

- `merged_branches`: 实际合并的分支数量
- `best_node_id`: 最佳节点的 ID
- `best_score`: 最佳节点分数

输出至 `research_traces`，可被 `scripts/visualize_equity_research_trace.py` 渲染。

---

## 5. 源码索引

| 文件 | 职责 |
|------|------|
| `agents/branch_merge.py` | 主实现 (`create_branch_merge`) |
| `prompts/rd_agent.py` (`thesis_merge_prompt`) | 合并 prompt 模板 |
| `state/schemas.py` (`Claim`, `ClaimType`) | Pydantic claim 模型 |
