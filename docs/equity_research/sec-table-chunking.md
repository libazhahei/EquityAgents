# SEC 表格感知分块 v2

> 语言：[中文](sec-table-chunking.md) | [English](../EQUITY_RESEARCH.md)  
> 相关文档：[SEC Filing RAG](sec-filing-rag.md) · [RAG 架构](../rag/architecture.md)

## 概述

SEC 表格感知分块 v2 解决了原有 RAG 系统只返回 1 个检索结果的问题。通过识别固定宽度的财务报表表格并按行拆分，同时采用更小的分块尺寸（300 词 vs 800 词），显著提升检索粒度与召回率。

## 问题背景

**原有问题**：搜索 "gross margin" 只返回 1 个 hit，即使文档中有多个相关段落。

**根本原因**：
- 分块尺寸过大（800 词/块）→ 单个 chunk 占用 `max_chars` 预算的大部分
- 表格内容被当作普通文本处理，整张表格（数千行）作为一个 chunk
- `max_chars` 截断策略过于严格，超出即停止

## 核心特性

### 1. 表格检测与分类

系统通过行级分类识别固定宽度表格：

| 行类型 | 检测规则 | 示例 |
|--------|----------|------|
| **SEPARATOR** | 连续 10+ 个 `━─\-–—=` | `─────────────────────────` |
| **DATA** | 行宽 >80 字符且远端（>60列）含数值 | `Cash and equivalents     $ 8,589    $ 7,280` |
| **LABEL** | 短文本或长文本无数值 | `Current assets:` |
| **BLANK** | 空行或纯空白 | |

**表格边界检测**：
- **起始**：SEPARATOR 行 或 连续 ≥2 行 DATA
- **结束**：连续 ≥2 行 BLANK 或 EOF
- **容错**：DATA 行之间允许 1-2 行 LABEL（行折行/层级标签/小计行）
- **最小表格**：≥3 行（含 SEPARATOR + DATA）

### 2. 层级标签追踪（Hierarchical Parent Label Tracking）

SEC 财报中常见层级结构：

```
Assets                                    ← 顶级标签
  Current assets:                         ← 二级标签
    Cash and cash equivalents  $ 8,589    ← 数据行
    Marketable securities       34,621    ← 数据行
  Non-current assets:                     ← 二级标签
    Property and equipment      6,283     ← 数据行
```

系统通过缩进量维护标签栈，确保拆分后的 chunk 保留上下文：

```python
[Chunk 2] 标题: "Consolidated Balance Sheets (continued)"
[Continued from: Assets, Current assets:]
    Accounts receivable, net    23,065
    Inventories                 10,080
```

### 3. 行级分块与重叠

**配置参数**（`default_config.py`）：
```python
"table_rows_per_chunk": 12,      # 每个子 chunk 12 行
"table_row_overlap": 2,          # 相邻 chunk 重叠 2 行
"table_context_paragraphs": 2,   # 前后各取 2 段上下文
```

**拆分示例**（30 行表格 → 3 个子 chunk）：
```
Chunk 1: rows 0-11
Chunk 2: rows 10-21  ← 与 Chunk 1 重叠 rows 10-11
Chunk 3: rows 20-29  ← 与 Chunk 2 重叠 rows 20-21
```

### 4. 上下文段落附加

每个表格子 chunk 底部附加前后各 2 个段落，提供业务背景：

```
[Table: Consolidated Balance Sheets]
Year Ended Jan 26, 2025 Jan 28, 2024
─────────────────────────────────────
Cash and cash equivalents     $ 8,589    $ 7,280
...
─────────────────────────────────────
Context: Item 8 presents our consolidated financial statements...
         See accompanying Notes to the Consolidated Financial Statements...
```

### 5. 段落级优化

`ParagraphChunker` 增强：
- **默认分块尺寸**：800 词 → **300 词**
- **句子级分割**：单段落超 300 词时按句号分割
- **硬分割兜底**：无句号的超长文本按词数硬切
- **重叠保留**：默认 100 词重叠

### 6. TOC 检测与过滤

避免目录页触发虚假 section 切换：

```python
# 检测规则：连续 ≥4 条 Item 行，相邻行间距 ≤3 行 → 判定为 TOC 块
TOC 示例：
  ITEM 1. BUSINESS
  ITEM 1A. RISK FACTORS
  ITEM 7. MANAGEMENT'S DISCUSSION
  ITEM 8. FINANCIAL STATEMENTS
```

### 7. 行首锚定正则

防止正文中 "Refer to Item 1A" 误触发 section 切换：

```python
# 旧正则（假阳性）
re.compile(r"\bITEM\s+1A[\.\s\-–—]*(RISK\s+FACTORS)?", re.I)

# 新正则（行首锚定 + 排除引用）
_EXCLUDE_PATTERN = re.compile(
    r"(?:refer\s+to|pursuant\s+to|see\s+|in\s+accordance\s+with).*Item", re.I
)
_ITEM_PATTERNS = [
    (re.compile(r"^\s*ITEM\s+1A[\.\s\-–—]", re.I), "risk_factors"),
    # ... 其他 Item
]
```

## 配置参数

### `tradingagents/default_config.py`

```python
"equity_research": {
    # 分块尺寸（词数）
    "filing_chunk_size": 300,           # 默认 300 词（原 800）
    "filing_chunk_overlap": 100,        # 重叠 100 词

    # 表格分块参数
    "table_rows_per_chunk": 12,         # 每个子 chunk 行数
    "table_row_overlap": 2,             # 行级重叠
    "table_context_paragraphs": 2,      # 上下文段落数

    # 检索参数
    "rag_search_max_chars": 16000,      # 最大字符数（原 8000）
    "rag_search_top_k": 8,              # Top-K 结果数
    "rag_search_pool_k": 30,            # 候选池大小

    # 分块器选择
    "sec_filing_chunker": "sec_item",   # 使用 SecItemChunker（内部集成 SecTableChunker）
}
```

## 数据流

```
SEC Filing (10-K/10-Q)
  ↓
SecItemChunker.chunk(text, metadata)
  ↓
  ├─ TOC 检测 → 跳过目录块
  ├─ detect_section(line) → 按 Item 分 section
  │
  └─ 每个 section → SecTableChunker.chunk(section_text, metadata)
       ↓
       ├─ _detect_table_regions(lines) → 识别表格边界
       ├─ _extract_table_title/headers → 提取元数据
       ├─ _split_table_body_into_rows → 层级标签追踪
       ├─ _split_rows → 按 12 行/块拆分 + 2 行重叠
       └─ 非表格文本 → ParagraphChunker（300 词/块）
```

## 输出示例

### Chunk Metadata

```python
{
    "doc_key": "0001045810-25-000012",
    "accession_number": "0001045810-25-000012",
    "ticker": "NVDA",
    "form": "10-K",
    "section": "financial_statements",
    "chunk_type": "table",              # 或 "text"
    "table_title": "Consolidated Balance Sheets",
    "table_section": "financial_statements",
    "parent_labels": ["Assets", "Current assets:"],
}
```

### Chunk Text 示例

```
[Chunk 1/3] section=financial_statements, chunk_type=table
            table_title="Consolidated Balance Sheets"
---
Consolidated Balance Sheets
(In millions, except par value)
Year Ended Jan 26, 2025 Jan 28, 2024
─────────────────────────────────────
Assets
Current assets:
Cash and cash equivalents     $ 8,589    $ 7,280
Marketable securities           34,621     18,704
...
Total current assets            80,126     44,345
---
Context: [前方段落] ... Item 8 presents our consolidated financial statements ...
         [后方段落] ... See accompanying Notes to the Consolidated Financial Statements ...

[Chunk 2/3] section=financial_statements, chunk_type=table
            table_title="Consolidated Balance Sheets"
            parent_context=["Assets"]
---
Consolidated Balance Sheets  (continued)
(In millions, except par value)
Year Ended Jan 26, 2025 Jan 28, 2024
─────────────────────────────────────
[Continued from: Assets]
Total current assets            80,126     44,345    ← 重叠行
Property and equipment, net      6,283      3,914
...
---
Context: [同 Chunk 1]
```

## 重新索引

### 为什么需要重新索引？

1. 分块逻辑已完全改变（表格感知 vs 纯段落）
2. 旧 chunks 缺少新 metadata 字段（`chunk_type`, `table_title`, `parent_labels`）
3. `is_stale()` 总是返回 `False`，系统会跳过已索引文档

### 如何重新索引

**选项 1：删除特定文档的旧 chunks**

```python
from tradingagents.rag.backends import create_backend

backend = create_backend(config, use_memory=False)
backend.delete_by_doc_key(
    table="filing_chunk",
    doc_key="0001045810-25-000012",  # 替换为你的 accession_number
    schema={"doc_key_column": "accession_number"}
)
```

**选项 2：清空整个表（PostgreSQL）**

```sql
-- 连接到数据库
psql -U postgres -d tradingagents_equity

-- 清空表
TRUNCATE TABLE filing_chunk;

-- 或只删除特定 ticker
DELETE FROM filing_chunk WHERE ticker = 'NVDA';
```

**选项 3：使用 `force_reindex` 参数（需实现）**

可在 `SecFilingsCorpus.is_stale()` 中添加强制重新索引逻辑：

```python
def is_stale(self, doc: Document, backend: Any) -> bool:
    # 检查配置中的 force_reindex 标志
    if self.config.get("equity_research", {}).get("force_reindex", False):
        return True
    return False
```

## 测试覆盖

### 单元测试（59 个测试全部通过）

- **`test_sec_table.py`**（22 个测试）
  - 表格检测、元数据提取、层级标签、分块逻辑

- **`test_sec_item.py`**（22 个测试）
  - Section 检测、TOC 过滤、集成测试

- **`test_paragraph.py`**（9 个测试）
  - 句子级分割、重叠、配置默认值

- **`test_chunking.py`**（6 个测试）
  - 注册表、基础功能

### 运行测试

```bash
cd /home/shilong/TradingAgents

# 运行所有分块测试
python -m pytest tests/rag/test_chunking.py \
                 tests/rag/test_sec_table.py \
                 tests/rag/test_sec_item.py \
                 tests/rag/test_paragraph.py -v

# 只运行表格测试
python -m pytest tests/rag/test_sec_table.py -v
```

## 性能对比

| 指标 | v1（原始） | v2（表格感知） | 改进 |
|------|-----------|---------------|------|
| 分块尺寸 | 800 词 | 300 词 | ↓62.5% |
| `max_chars` | 8000 | 16000 | ↑100% |
| 搜索 "gross margin" 命中数 | 1 | 3-5 | ↑200-400% |
| 表格 chunk 元数据 | ❌ | ✅ `chunk_type`, `table_title` | 新增 |
| 层级上下文 | ❌ | ✅ `parent_labels`, `[Continued from:]` | 新增 |
| 行级重叠 | ❌ | ✅ 2 行重叠 | 新增 |
| TOC 过滤 | ❌ | ✅ 自动检测 | 新增 |

## 代码位置

| 组件 | 路径 | 职责 |
|------|------|------|
| **SecTableChunker** | `tradingagents/rag/chunking/sec_table.py` | 表格检测、层级标签、行级分块 |
| **ParagraphChunker** | `tradingagents/rag/chunking/paragraph.py` | 句子级分割、硬分割兜底 |
| **SecItemChunker** | `tradingagents/rag/chunking/sec_item.py` | TOC 检测、section 切换、集成 SecTableChunker |
| **注册表** | `tradingagents/rag/chunking/__init__.py` | `CHUNKERS` dict、`get_chunker()` |
| **配置** | `tradingagents/default_config.py` | 默认参数 |
| **服务层** | `tradingagents/rag/service.py` | `max_chars` 截断策略 |
| **测试** | `tests/rag/test_sec_table.py` 等 | 59 个单元测试 |

## 故障排查

### 问题：搜索仍只返回 1 个 hit

**原因**：旧 chunks 未重新索引。

**解决**：
```sql
TRUNCATE TABLE filing_chunk;
-- 然后重新运行 ingest
```

### 问题：表格未被检测

**原因**：行宽 <80 字符或无数值列。

**诊断**：
```python
from tradingagents.rag.chunking.sec_table import _classify_line, _LineKind

line = "Your table row here"
kind = _classify_line(line)
print(f"Line type: {kind}")  # 应为 DATA 或 SEPARATOR
```

### 问题：层级标签不正确

**原因**：缩进量不符合预期。

**诊断**：
```python
from tradingagents.rag.chunking.sec_table import _split_table_body_into_rows

rows = _split_table_body_into_rows(lines, table_start, table_end)
for raw_line, kind, parent_ctx in rows:
    if parent_ctx:
        print(f"{raw_line} → parent: {parent_ctx}")
```

## 延伸阅读

| 资源 | 路径 |
|------|------|
| SEC Filing RAG 总体设计 | [sec-filing-rag.md](sec-filing-rag.md) |
| RAG 架构 | [../rag/architecture.md](../rag/architecture.md) |
| ParadeDB BM25 配置 | [storage.md](storage.md) § PostgreSQL |
| 证据向量存储 | [storage.md](storage.md) § EvidenceStore |

## 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v2.0 | 2026-07-07 | 表格感知分块、层级标签、行级重叠、TOC 过滤 |
| v1.0 | 2025-xx-xx | 初始段落分块（800 词/块） |
