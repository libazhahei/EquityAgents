一个 **“Section Question Tree Compiler”**。

它当前只做一件事：

> 给定一个 equity research section，结合 template 的 required outputs 和已有背景材料，生成一个完整、可执行、可交给后续 agent loop 的研究问题树。

它不写正文、不深度研究、不持续 loop。  
它可以有轻量 web search，但只用于 **grounding / 补洞 / 避免明显过时**，不用于完成研究。

---

# 1. 这个 Planner 的定位

你的目标可以抽象为：

```text
输入：
- ticker
- section_id
- section_title
- required_outputs
- 背景报告，例如 consensus_report / final_report
- 可选 user_focus，例如“市场预期与一致观点”

输出：
- root question
- sub questions
- sub-sub questions
- 每个问题对应的 required evidence
- suggested sources
- downstream agent hint
- required_outputs 到问题节点的 coverage_map
```

换句话说：

```text
Planner = section schema + background reports → executable research question tree
```

不是：

```text
Planner = search → think → search → answer
```

所以它不应该是纯 ReAct。更合适的是：

```text
Structured Planning Pass
+ optional light grounding
+ JSON schema constrained output
```

---

# 2. 为什么不要纯 ReAct

纯 ReAct 的缺点是：

1. 会过早被搜索结果牵引；
2. 容易变成“查到什么写什么”；
3. 很难保证覆盖 template 里的所有 required_outputs；
4. 很难输出稳定、可被后续 loop 消费的结构；
5. 不适合做“问题空间设计”。

Planner 需要的是一次高质量的结构化生成：

```text
section intent → assumptions/existing debates → research questions → evidence plan
```

如果要引入 search，也应该只放在 planner 前半段，做轻量补充：

```text
optional web_search:
- latest earnings call key debates
- latest consensus estimate drivers
- latest section-specific company news
```

然后再统一规划，而不是边规划边深搜。

---

# 3. 推荐架构

## 总流程

```text
SectionPlannerRequest
        ↓
1. Template Interpreter
        ↓
2. Background Extractor
        ↓
3. Optional Light Grounding Search
        ↓
4. Question Tree Generator
        ↓
5. Coverage Validator
        ↓
6. Serializable SectionResearchPlan
```

## 每一步职责

### 1）Template Interpreter

根据 `section_id` 和 `required_outputs` 判断这个章节到底要解决什么。

例如：

```python
"4_industry_and_competition"
```

目标是回答：

- TAM 多大？
- 行业增速多少？
- 产业链位置如何？
- 市占率如何？
- 竞争对手是谁？
- 护城河在哪里？
- 监管政策有什么影响？

### 2）Background Extractor

从你给的 `consensus_report` / `final_report` 里抽取：

- 市场隐含假设；
- 争议点；
- model drivers；
- evidence for / against；
- falsification tests；
- next data to watch。

对于 NVDA，你的背景材料里已经有很好的假设：

- hyperscaler capex 持续至 FY26–FY27；
- Blackwell ramps on time；
- gross margin stays low-to-mid 70s；
- NVDA preserves dominant AI accelerator share；
- competitive/regulatory friction only gradual。

### 3）Optional Light Grounding

只在需要时做少量 web search。

目的不是完成研究，而是帮助 planner：

- 判断有没有重大遗漏；
- 补充最新关键词；
- 防止已经过时；
- 为后续 loop 提供搜索入口。

例如：

```text
NVDA latest earnings call AI capex Blackwell margin competition
NVDA AMD custom silicon market share AI accelerator 2026
NVDA export controls China data center revenue
```

### 4）Question Tree Generator

LLM 根据：

- section intent；
- required_outputs；
- extracted assumptions；
- optional grounding notes；

生成问题树。

### 5）Coverage Validator

检查每一个 required_output 是否至少被一个 question node 覆盖。

比如 `4_industry_and_competition` 的：

```python
[
  "tam_estimate",
  "industry_growth_rate",
  "value_chain_analysis",
  "market_share_analysis",
  "competitor_comparison_table",
  "competitive_position_assessment",
  "regulatory_or_policy_factors",
]
```

都必须映射到问题节点。

### 6）Serializable Plan

最后输出一个可序列化 JSON，塞进你现有的 `ExplorationNode.structured_view_snapshot`。

---

# 4. 核心数据结构

## 4.1 Planner Request

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SectionPlannerRequest:
    ticker: str
    section_id: str
    section_title: str
    required_outputs: list[str]
    background_reports: dict[str, str] = field(default_factory=dict)
    user_focus: str | None = None
    time_horizon: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    extra_context: dict[str, Any] = field(default_factory=dict)
```

示例：

```python
req = SectionPlannerRequest(
    ticker="NVDA",
    section_id="4_industry_and_competition",
    section_title="Industry Analysis & Competitive Landscape",
    required_outputs=[
        "tam_estimate",
        "industry_growth_rate",
        "value_chain_analysis",
        "market_share_analysis",
        "competitor_comparison_table",
        "competitive_position_assessment",
        "regulatory_or_policy_factors",
    ],
    background_reports={
        "consensus_report": consensus_report,
        "final_report": final_report,
    },
    user_focus="市场预期与一致观点",
    time_horizon="FY26-FY27",
    allowed_tools=["web_search"],
)
```

---

## 4.2 Question Node

```python
@dataclass
class ResearchQuestionNode:
    id: str
    parent_id: str | None
    level: int
    question: str

    # 这个问题为什么应该出现在这个 section
    rationale: str

    # 数字越小越优先，或者你也可以反过来
    priority: int

    # 后续 research loop 需要拿什么证据回答
    required_evidence: list[str] = field(default_factory=list)

    # 建议数据源
    suggested_sources: list[str] = field(default_factory=list)

    # 这个问题最后应该产出什么
    expected_output: str = ""

    # 未来扩展：交给哪个 agent loop
    downstream_agent: str | None = None

    # 给后续 loop 的停止建议，不是 planner 自己执行
    stop_condition_hint: str | None = None
```

---

## 4.3 Final Plan

```python
@dataclass
class SectionResearchPlan:
    ticker: str
    section_id: str
    section_title: str

    # 一句话说明本章节规划的核心分析角度
    planning_thesis: str

    # 整个 section 的总问题
    root_question: str

    # tree nodes
    nodes: list[ResearchQuestionNode]

    # required_output -> question node ids
    coverage_map: dict[str, list[str]]

    # 后续 loop 推荐执行顺序
    execution_order: list[str]

    # 背景材料/搜索发现中的问题
    data_quality_flags: list[str] = field(default_factory=list)

    planner_notes: str | None = None
```

---

# 5. Prompt 设计

这是 planner 最关键的部分。

建议使用一个强约束 prompt：

```text
You are an equity research section planner.

Your job is NOT to write the report section.
Your job is to create an executable research question tree for ONE section of a professional equity research report.

Inputs:
- ticker
- section_id
- section_title
- required_outputs
- background reports
- optional user_focus and time_horizon

You must:
1. Identify the analytical purpose of this section.
2. Extract section-relevant assumptions, controversies, model drivers, and evidence gaps from the background.
3. Generate exactly one root question.
4. Generate 3 to 7 mandatory sub-questions.
5. Generate sub-sub-questions only when they clarify evidence collection.
6. Every question must be concrete, researchable, and evidence-seeking.
7. Map every required_output to at least one question node in coverage_map.
8. Provide execution_order from highest priority to lowest priority.
9. Provide data_quality_flags if the input background is incomplete, duplicated, stale, or internally inconsistent.
10. Do not produce final prose.
11. Do not invent verified facts. Mark uncertain facts as "needs verification".

Return strict JSON only.
```

---

# 6. 推荐加入 section intent hints

你不用给 10 个 section 各写一个 planner，但建议加非常轻的 hints。

```python
SECTION_INTENT_HINTS = {
    "1_investment_summary": (
        "Focus on investment rating, target price, current price, expected return, "
        "core thesis, variant view, and catalyst timeline. This section should synthesize "
        "other sections rather than introduce unsupported new analysis."
    ),
    "2_company_overview": (
        "Focus on business identity, corporate history, ownership, management, "
        "segment mix, geographic mix, and major transformation milestones."
    ),
    "3_business_model": (
        "Focus on how the company makes money, revenue mechanics, pricing model, "
        "customers/channels, unit economics, operating metrics, and margin drivers."
    ),
    "4_industry_and_competition": (
        "Focus on TAM, industry growth, value chain position, market share, competitor comparison, "
        "competitive moat, substitution risk, and regulation."
    ),
    "5_historical_financials": (
        "Focus on revenue growth history, segment performance, gross margin, operating margin, "
        "cash flow, balance sheet quality, and return metrics."
    ),
    "6_earnings_forecast": (
        "Focus on forward financial assumptions, segment revenue forecast, gross margin, opex, "
        "EBITDA, net income, EPS, FCF, and explicit key assumptions."
    ),
    "7_valuation": (
        "Focus on valuation method rationale, peer set, historical multiples, DCF or target multiple "
        "assumptions, target price calculation, implied upside/downside, and rating explanation."
    ),
    "8_scenario_and_sensitivity": (
        "Focus on bull/base/bear assumptions, target price range, and sensitivity to the key variables "
        "that drive valuation."
    ),
    "9_risks": (
        "Focus on company-specific risks, industry risks, macro risks, thesis-breaking risks, "
        "counter-evidence, and what would change the investment view."
    ),
    "10_appendix": (
        "Focus on source list, model notes, data quality flags, methodology notes, and disclaimers."
    ),
}
```

Prompt 里加：

```text
Section intent hint: {SECTION_INTENT_HINTS[section_id]}
```

这会极大降低跑偏概率。

---

# 7. 完整 Planner 实现骨架

下面是一个可以直接落地的版本。

```python
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Callable
import json
import re
import uuid


SECTION_INTENT_HINTS = {
    "1_investment_summary": (
        "Focus on investment rating, target price, current price, expected return, "
        "core thesis, variant view, and catalyst timeline. This section should synthesize "
        "other sections rather than introduce unsupported new analysis."
    ),
    "2_company_overview": (
        "Focus on business identity, corporate history, ownership, management, "
        "segment mix, geographic mix, and major transformation milestones."
    ),
    "3_business_model": (
        "Focus on how the company makes money, revenue mechanics, pricing model, "
        "customers/channels, unit economics, operating metrics, and margin drivers."
    ),
    "4_industry_and_competition": (
        "Focus on TAM, industry growth, value chain position, market share, competitor comparison, "
        "competitive moat, substitution risk, and regulation."
    ),
    "5_historical_financials": (
        "Focus on revenue growth history, segment performance, gross margin, operating margin, "
        "cash flow, balance sheet quality, and return metrics."
    ),
    "6_earnings_forecast": (
        "Focus on forward financial assumptions, segment revenue forecast, gross margin, opex, "
        "EBITDA, net income, EPS, FCF, and explicit key assumptions."
    ),
    "7_valuation": (
        "Focus on valuation method rationale, peer set, historical multiples, DCF or target multiple "
        "assumptions, target price calculation, implied upside/downside, and rating explanation."
    ),
    "8_scenario_and_sensitivity": (
        "Focus on bull/base/bear assumptions, target price range, and sensitivity to the key variables "
        "that drive valuation."
    ),
    "9_risks": (
        "Focus on company-specific risks, industry risks, macro risks, thesis-breaking risks, "
        "counter-evidence, and what would change the investment view."
    ),
    "10_appendix": (
        "Focus on source list, model notes, data quality flags, methodology notes, and disclaimers."
    ),
}


@dataclass
class SectionPlannerRequest:
    ticker: str
    section_id: str
    section_title: str
    required_outputs: list[str]
    background_reports: dict[str, str] = field(default_factory=dict)
    user_focus: str | None = None
    time_horizon: str | None = None
    allowed_tools: list[str] = field(default_factory=list)
    extra_context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchQuestionNode:
    id: str
    parent_id: str | None
    level: int
    question: str
    rationale: str
    priority: int
    required_evidence: list[str] = field(default_factory=list)
    suggested_sources: list[str] = field(default_factory=list)
    expected_output: str = ""
    downstream_agent: str | None = None
    stop_condition_hint: str | None = None


@dataclass
class SectionResearchPlan:
    ticker: str
    section_id: str
    section_title: str
    planning_thesis: str
    root_question: str
    nodes: list[ResearchQuestionNode]
    coverage_map: dict[str, list[str]]
    execution_order: list[str]
    data_quality_flags: list[str] = field(default_factory=list)
    planner_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EquitySectionPlanner:
    def __init__(
        self,
        llm: Callable[[str], str],
        search_func: Callable[[str], list[str]] | None = None,
        max_background_chars: int = 20000,
    ) -> None:
        self.llm = llm
        self.search_func = search_func
        self.max_background_chars = max_background_chars

    def plan(self, req: SectionPlannerRequest) -> SectionResearchPlan:
        background = self._pack_background(req)

        grounding_notes = ""
        if self.search_func and "web_search" in req.allowed_tools:
            grounding_notes = self._light_grounding(req)

        prompt = self._build_prompt(req, background, grounding_notes)
        raw = self.llm(prompt)
        data = self._parse_json(raw)

        data = self._normalize_plan_dict(data, req)
        data = self._validate_and_repair(data, req)

        return self._to_plan(data)

    def _pack_background(self, req: SectionPlannerRequest) -> str:
        parts = []

        for name, text in req.background_reports.items():
            if text:
                parts.append(f"## {name}\n{text}")

        packed = "\n\n".join(parts)
        return packed[: self.max_background_chars]

    def _light_grounding(self, req: SectionPlannerRequest) -> str:
        """
        轻量 grounding，不做完整研究。
        只用于帮助 planner 避免遗漏明显的近期争议。
        """
        queries = [
            f"{req.ticker} latest earnings call key debates",
            f"{req.ticker} consensus estimates key assumptions",
            f"{req.ticker} {req.section_title} latest developments",
        ]

        section_specific = {
            "4_industry_and_competition": [
                f"{req.ticker} market share competitors latest",
                f"{req.ticker} industry growth TAM competition latest",
            ],
            "5_historical_financials": [
                f"{req.ticker} historical revenue gross margin cash flow trend",
            ],
            "6_earnings_forecast": [
                f"{req.ticker} guidance analyst consensus revenue EPS forecast",
            ],
            "7_valuation": [
                f"{req.ticker} valuation multiple peer comparison target price consensus",
            ],
            "9_risks": [
                f"{req.ticker} key risks regulatory competition latest",
            ],
        }

        queries.extend(section_specific.get(req.section_id, []))

        snippets = []
        for q in queries[:5]:
            try:
                results = self.search_func(q) or []
                snippets.append(f"Query: {q}\n" + "\n".join(results[:3]))
            except Exception as e:
                snippets.append(f"Query: {q}\nERROR: {e}")

        return "\n\n".join(snippets)

    def _build_prompt(
        self,
        req: SectionPlannerRequest,
        background: str,
        grounding_notes: str,
    ) -> str:
        section_hint = SECTION_INTENT_HINTS.get(req.section_id, "")

        schema_hint = {
            "ticker": req.ticker,
            "section_id": req.section_id,
            "section_title": req.section_title,
            "planning_thesis": "string",
            "root_question": "string",
            "nodes": [
                {
                    "id": "q0",
                    "parent_id": None,
                    "level": 0,
                    "question": "string",
                    "rationale": "string",
                    "priority": 1,
                    "required_evidence": ["string"],
                    "suggested_sources": ["string"],
                    "expected_output": "string",
                    "downstream_agent": "string_or_null",
                    "stop_condition_hint": "string_or_null",
                }
            ],
            "coverage_map": {
                output: ["q_id"] for output in req.required_outputs
            },
            "execution_order": ["q0"],
            "data_quality_flags": ["string"],
            "planner_notes": "string_or_null",
        }

        return f"""
You are an equity research section planner.

Your job is NOT to write the report section.
Your job is to create an executable research question tree for ONE section of a professional equity research report.

INPUTS:
Ticker: {req.ticker}
Section ID: {req.section_id}
Section Title: {req.section_title}
Section Intent Hint: {section_hint or "None"}
Required Outputs: {req.required_outputs}
User Focus: {req.user_focus or "None"}
Time Horizon: {req.time_horizon or "Not specified"}
Extra Context: {json.dumps(req.extra_context, ensure_ascii=False)}

BACKGROUND REPORTS:
{background or "No background provided."}

OPTIONAL LIGHT GROUNDING NOTES:
{grounding_notes or "None"}

TASK:
1. Identify the analytical purpose of this section.
2. Extract section-relevant assumptions, controversies, model drivers, and evidence gaps from the background.
3. Generate exactly one root question for this section.
4. Generate 3 to 7 mandatory sub-questions.
5. Generate sub-sub-questions only if they are necessary for evidence collection.
6. Every question must be concrete, researchable, and evidence-seeking.
7. Map every required_output to at least one question node in coverage_map.
8. Provide execution_order from highest priority to lowest priority.
9. Provide data_quality_flags if the input background is incomplete, duplicated, stale, truncated, or internally inconsistent.
10. Do not write final prose.
11. Do not invent verified facts. If a fact is uncertain or only suggested by background, mark it as "needs verification".
12. The plan should be usable by downstream research agents.

Return STRICT JSON only. No markdown. No explanations.

JSON schema example:
{json.dumps(schema_hint, ensure_ascii=False, indent=2)}
""".strip()

    def _parse_json(self, raw: str) -> dict[str, Any]:
        raw = raw.strip()

        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        cleaned = re.sub(r"^```json\s*", "", raw)
        cleaned = re.sub(r"^```\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
        if match:
            return json.loads(match.group(0))

        raise ValueError("Planner LLM did not return valid JSON.")

    def _normalize_plan_dict(
        self,
        data: dict[str, Any],
        req: SectionPlannerRequest,
    ) -> dict[str, Any]:
        data.setdefault("ticker", req.ticker)
        data.setdefault("section_id", req.section_id)
        data.setdefault("section_title", req.section_title)
        data.setdefault("planning_thesis", "")
        data.setdefault("root_question", "")
        data.setdefault("nodes", [])
        data.setdefault("coverage_map", {})
        data.setdefault("execution_order", [])
        data.setdefault("data_quality_flags", [])
        data.setdefault("planner_notes", None)

        if not isinstance(data["nodes"], list):
            data["nodes"] = []

        if not data["nodes"]:
            root_id = "q0"
            root_question = data.get("root_question") or (
                f"What must be researched to complete {req.section_title} for {req.ticker}?"
            )
            data["root_question"] = root_question
            data["nodes"] = [
                {
                    "id": root_id,
                    "parent_id": None,
                    "level": 0,
                    "question": root_question,
                    "rationale": "Auto-filled root node because planner returned no valid nodes.",
                    "priority": 1,
                    "required_evidence": req.required_outputs,
                    "suggested_sources": [],
                    "expected_output": req.section_title,
                    "downstream_agent": None,
                    "stop_condition_hint": None,
                }
            ]

        # 确保第一个 node 是 root-like
        if not data.get("root_question"):
            data["root_question"] = data["nodes"][0].get("question", "")

        seen = set()
        root_id = data["nodes"][0].get("id", "q0")

        for i, node in enumerate(data["nodes"]):
            if not isinstance(node, dict):
                node = {}
                data["nodes"][i] = node

            node.setdefault("id", f"q{i}")

            if node["id"] in seen:
                node["id"] = f"{node['id']}_{uuid.uuid4().hex[:4]}"

            seen.add(node["id"])

            node.setdefault("parent_id", None if i == 0 else root_id)
            node.setdefault("level", 0 if i == 0 else 1)
            node.setdefault("question", "")
            node.setdefault("rationale", "")
            node.setdefault("priority", i + 1)
            node.setdefault("required_evidence", [])
            node.setdefault("suggested_sources", [])
            node.setdefault("expected_output", "")
            node.setdefault("downstream_agent", None)
            node.setdefault("stop_condition_hint", None)

            if not isinstance(node["required_evidence"], list):
                node["required_evidence"] = [str(node["required_evidence"])]

            if not isinstance(node["suggested_sources"], list):
                node["suggested_sources"] = [str(node["suggested_sources"])]

        node_ids = {n["id"] for n in data["nodes"]}

        # execution_order fallback
        if not data["execution_order"]:
            data["execution_order"] = [
                n["id"]
                for n in sorted(
                    data["nodes"],
                    key=lambda x: int(x.get("priority", 999)),
                )
            ]
        else:
            data["execution_order"] = [
                qid for qid in data["execution_order"] if qid in node_ids
            ]
            if not data["execution_order"]:
                data["execution_order"] = [data["nodes"][0]["id"]]

        # coverage_map fallback
        if not isinstance(data["coverage_map"], dict):
            data["coverage_map"] = {}

        for output in req.required_outputs:
            ids = data["coverage_map"].get(output)

            if isinstance(ids, str):
                ids = [ids]

            if not ids:
                data["coverage_map"][output] = [data["nodes"][0]["id"]]
            else:
                valid_ids = [qid for qid in ids if qid in node_ids]
                data["coverage_map"][output] = valid_ids or [data["nodes"][0]["id"]]

        return data

    def _validate_and_repair(
        self,
        data: dict[str, Any],
        req: SectionPlannerRequest,
    ) -> dict[str, Any]:
        flags = data.setdefault("data_quality_flags", [])

        # 检查 required_outputs coverage
        missing_outputs = [
            output
            for output in req.required_outputs
            if output not in data.get("coverage_map", {}) or not data["coverage_map"][output]
        ]
        if missing_outputs:
            flags.append(f"coverage_map_missing_outputs: {missing_outputs}")
            for output in missing_outputs:
                data["coverage_map"][output] = [data["nodes"][0]["id"]]

        # 检查节点数量
        level_1_nodes = [n for n in data["nodes"] if int(n.get("level", 0)) == 1]
        if len(level_1_nodes) < 3:
            flags.append("planner_generated_fewer_than_3_sub_questions")
        if len(level_1_nodes) > 7:
            flags.append("planner_generated_more_than_7_sub_questions")

        # 检查问题是否为空
        empty_questions = [n["id"] for n in data["nodes"] if not n.get("question")]
        if empty_questions:
            flags.append(f"empty_question_nodes: {empty_questions}")

        return data

    def _to_plan(self, data: dict[str, Any]) -> SectionResearchPlan:
        nodes = [
            ResearchQuestionNode(
                id=n["id"],
                parent_id=n.get("parent_id"),
                level=int(n.get("level", 0)),
                question=n.get("question", ""),
                rationale=n.get("rationale", ""),
                priority=int(n.get("priority", 1)),
                required_evidence=list(n.get("required_evidence", [])),
                suggested_sources=list(n.get("suggested_sources", [])),
                expected_output=n.get("expected_output", ""),
                downstream_agent=n.get("downstream_agent"),
                stop_condition_hint=n.get("stop_condition_hint"),
            )
            for n in data["nodes"]
        ]

        return SectionResearchPlan(
            ticker=data["ticker"],
            section_id=data["section_id"],
            section_title=data["section_title"],
            planning_thesis=data["planning_thesis"],
            root_question=data["root_question"],
            nodes=nodes,
            coverage_map=data["coverage_map"],
            execution_order=data["execution_order"],
            data_quality_flags=data.get("data_quality_flags", []),
            planner_notes=data.get("planner_notes"),
        )
```

---

# 8. 如何把 planner 存成你现有 ExplorationGraph 的一个 node

你前面说：

> 我只想用一个 node 来做一个完整的前期 planner。

那就这样：

```python
from dataclasses import asdict

planner_node = graph.new_node(
    parent_id=None,
    branch_id=f"{req.ticker}_{req.section_id}_planner",
)

planner_node.structured_view_snapshot = {
    "type": "section_research_plan",
    "plan": plan.to_dict(),
}

planner_node.query_plan = [
    {
        "question_id": node.id,
        "parent_id": node.parent_id,
        "level": node.level,
        "question": node.question,
        "priority": node.priority,
        "required_evidence": node.required_evidence,
        "suggested_sources": node.suggested_sources,
        "expected_output": node.expected_output,
        "downstream_agent": node.downstream_agent,
        "stop_condition_hint": node.stop_condition_hint,
    }
    for node in plan.nodes
]

planner_node.coverage_score = 1.0 if not plan.data_quality_flags else 0.8
planner_node.routing_decision = "ready_for_research_loop"
```

这样你的 `ExplorationGraph` 不需要大改。  
Planner 作为一个起始 node，后面的 loop 读取 `query_plan`，按 `execution_order` 调用不同 agent loop。

---

# 9. NVDA 示例：Industry & Competition

如果给你现在的 NVDA 背景，section 是：

```python
"4_industry_and_competition"
```

合理的 planner 输出应该类似：

```text
Root Question:
Can NVIDIA sustain its dominant position in AI infrastructure through FY26–FY27, or will capex digestion, supply-chain bottlenecks, custom silicon, AMD competition, and regulatory friction erode the consensus growth path?
```

问题树：

```text
NVDA 能否在 FY26–FY27 继续维持 AI infrastructure 主导地位？
├── AI infrastructure TAM 和行业增速是否足以支撑当前共识？
│   ├── hyperscaler capex 是否仍处于上行周期？
│   ├── 训练需求、推理需求、主权 AI 和企业 AI 各自贡献多少增量？
│   └── 行业增速是否已经隐含了过度线性外推？
├── 产业链瓶颈是否限制 NVDA 把需求转化为收入？
│   ├── HBM、CoWoS、先进封装和液冷/机架集成的约束在哪里？
│   └── Blackwell 到 Rubin 的过渡是否有交付节奏风险？
├── NVDA 的 AI accelerator 份额是否会被竞争对手稀释？
│   ├── AMD MI 系列在哪些 workload 具备替代性？
│   ├── hyperscaler custom ASIC 会优先替代训练还是推理？
│   └── Intel、中国国产芯片和其他替代方案的实际威胁有多大？
├── NVDA 的护城河来自哪里，是否仍然有效？
│   ├── CUDA、软件生态和开发者锁定是否仍是核心壁垒？
│   ├── networking、systems、rack-scale solution 是否提高切换成本？
│   └── 客户是否正在主动降低对 NVDA 的依赖？
├── 竞争格局是否会影响定价权和毛利率？
│   ├── 产品从芯片转向系统级方案是否稀释毛利率？
│   ├── 大客户集中度是否削弱 NVDA 议价能力？
│   └── 竞争最可能先体现在 ASP、share 还是 margin？
└── 监管和地缘政治限制会削弱哪些需求池？
    ├── 中国出口限制对可服务 TAM、收入和 margin 的影响多大？
    ├── 中东/主权 AI 订单是否存在审批或交付不确定性？
    └── 本土替代会不会在部分区域形成长期 share pressure？
```

这就已经是一个非常好的 planner 产物。后面每个节点都能变成一个 loop 任务。

---

# 10. AWS 历史章节示例应该如何规划

你给的 AWS / Amazon historical section 例子，对应 section 大概率是：

```python
"2_company_overview"
```

或者：

```python
"5_historical_financials"
```

如果是综合“历史+财务复盘”，planner 应生成的问题树：

```text
Root Question:
Amazon 如何从电商平台演化为由电商、物流、AWS、广告和硬件共同构成的综合科技公司，而这种演化如何体现在历史财务表现中？

├── Amazon 的业务身份和战略定位如何演变？
│   ├── 早期电商平台模式如何建立用户规模和品类扩张？
│   ├── Prime、Marketplace、FBA 如何改变商业模式？
│   └── 广告、订阅和第三方卖家服务如何提高货币化能力？
├── 自建物流体系如何形成竞争壁垒？
│   ├── 仓储、履约、配送和最后一公里网络如何演进？
│   ├── 重资产投入如何影响短期 margin 和长期效率？
│   └── 物流网络如何增强 Prime 和 Marketplace 飞轮？
├── AWS 的创立如何改变 Amazon 的公司属性？
│   ├── AWS 从内部基础设施能力如何演变为云服务业务？
│   ├── AWS 对收入增速、利润率和估值框架的影响是什么？
│   └── AWS 如何推动 Amazon 从电商公司转向综合科技平台？
├── Amazon 的硬件和设备业务有哪些战略意义与挑战？
│   ├── Kindle、Echo、Fire、Ring 等产品承担什么生态入口角色？
│   ├── 硬件业务的商业化和利润贡献为何有限？
│   └── AI assistant 和 smart home 是否改变硬件业务价值？
├── 历史财务表现可以分为哪些阶段？
│   ├── 2001–2010：重资产物流投入与供应链差异化形成
│   ├── 2010–2020：AWS 驱动利润结构和估值逻辑重塑
│   ├── 2020–至今：疫情繁荣、后疫情低谷、广告和 AI 修复增长
│   └── 每个阶段的 revenue growth、margin、FCF、capex 有何特征？
└── 股权结构和管理团队如何影响战略延续性？
    ├── 创始人影响力和管理层交接如何影响资本配置？
    ├── 当前核心管理团队的背景和战略重点是什么？
    └── 股东结构是否支持长期投资导向？
```

这说明 planner 不需要靠手工预定义 NVDA 或 AWS 的树，它只要理解：

- section intent；
- required_outputs；
- 背景材料；
- equity research 关心什么。

---

# 11. Planner 的停止条件

Planner 自身的停止条件不要复杂化。

只要满足以下条件即可停止：

1. 有且只有一个 `root_question`；
2. 有 3–7 个一级 `sub_questions`；
3. 必要问题有二级 `sub-sub_questions`；
4. 所有 `required_outputs` 都在 `coverage_map` 中被覆盖；
5. 每个问题有：
   - rationale；
   - required_evidence；
   - suggested_sources；
   - expected_output；
6. 输出是合法 JSON；
7. 如果背景不足，写入 `data_quality_flags`，而不是继续无限搜索。

真正的“边际收益递减停止”留给后续 research loop，不要塞进 planner。

---

# 12. 最终建议

你的 planner 最好保持为：

```text
单 node
无长期状态
schema-constrained
section-aware
background-aware
lightly grounded
question-tree output
```

