好的，我仔细读完了你的代码库和论文。让我梳理一下核心设计思路。

---

## 当前问题诊断

你的 `consensus_subgraph` 本质上是一个**硬编码的单任务 DAG**：

- 节点名称全是 `consensus_*` 前缀，业务逻辑和框架逻辑完全耦合
- Skills、Planner、Executor、Reflector 都是为 consensus 定制的，无法复用到 `fundamental_analysis`、`risk_assessment` 等其他研究环节
- 没有树状探索，只有线性 loop（coverage_reflector → gap_planner → executor 的单链）
- ExplorationGraph 概念缺失，每次 loop 的历史状态只是简单的 `search_memory` list

---


---

## 核心抽象层设计

### Layer 0：TaskProfile（任务描述，纯数据）

```python
@dataclass
class TaskProfile:
    task_id: str               # "consensus", "fundamental", "risk"
    objective: str             # 自然语言目标
    dimensions: list[str]      # 需要覆盖的维度
    output_schema: type        # Pydantic model，定义结构化输出
    default_queries_fn: callable  # 冷启动 query 生成器
    coverage_threshold: float  # 何时认为"足够好"
    max_iterations: int
    skill_objective: str       # 传给 SkillSelector 的 objective hint
```

`ConsensusTaskProfile` 只是 `TaskProfile` 的一个实例，不再是硬编码节点。

---

### Layer 2：AgentState（通用状态，不含业务字段）

这是最关键的解耦点。现在你的 `ConsensusSubgraphState` 里有大量 `consensus_*` 字段，未来会有 `fundamental_*`、`risk_*`……

重构成：

```python
class AgentState(TypedDict):
    # === 任务描述 ===
    task_profile: dict              # TaskProfile.model_dump()
    ticker: str
    
    # === 探索图 ===
    exploration_graph: dict         # ExplorationGraph 序列化
    current_branch_id: str
    
    # === 通用 loop 状态 ===
    active_skill_context: dict
    query_queue: list[dict]         # 待执行的 QueryItem list
    pending_evidence: list[dict]    # 本轮执行结果
    search_memory: list[dict]       # 全量历史（跨 loop）
    
    # === 结构化输出（由 output_schema 决定）===
    structured_view: dict           # StructuredConsensusView / StructuredFundamentalView
    coverage_report: dict
    coverage_history: list[dict]
    
    # === 假设层（可选，由 TaskProfile 控制是否启用）===
    assumptions: dict
    
    # === 最终产物 ===
    final_report: str
    
    # === 系统字段 ===
    iterations: int
    max_iterations: int
    errors: list[str]
    compliance_flags: list[dict]
    human_review_payload: dict
```

`consensus_view`、`consensus_report` 统一变成 `structured_view`、`final_report`。

---

### Layer 3：ExplorationGraph（参照 R&D-Agent 的 G）

论文里最核心的数据结构，对应 Algorithm 1 中的 `G`：

```python
@dataclass
class ExplorationNode:
    node_id: str
    parent_id: str | None
    branch_id: str
    
    # Research 产物
    query_plan: list[dict]
    evidence: list[dict]
    
    # Development 产物（对你来说是 synthesis 结果，以及可能搜索的结构，以及根据研究得到的数据预测）
    structured_view_snapshot: dict
    coverage_score: float
    
    # 元数据
    iteration: int
    created_at: str

class ExplorationGraph:
    nodes: dict[str, ExplorationNode]
    
    def select_parents(self, strategy="greedy") -> list[str]:
        """对应论文 SelectParents，greedy = 取最高 coverage_score"""
    
    def add_node(self, node: ExplorationNode): ...
    
    def best_node(self) -> ExplorationNode:
        """最终选 submit 哪个 branch"""
    
    def to_chain(self) -> list[ExplorationNode]:
        """退化成线性 loop，向后兼容"""
```

当前你只需要 chain，但这个抽象让你后续可以切换到 tree search（多个 branch 并行，分别从不同 parent 出发）。

---

### Layer 4：通用节点工厂（Plan / Execute / Reflect）

六个通用节点，全部接受 `TaskProfile` 作为参数：

```python
# 1. PlannerNode —— 对应 R&D-Agent FC-Planning + FC-ReasoningPipeline
def create_planner_node(deps, task_profile: TaskProfile, mode="initial|loop"):
    """
    mode=initial: 冷启动，生成全量 query
    mode=loop:    gap planning，生成 ≤2 个补充 query
    
    prompt 里用 task_profile.dimensions / objective 替代硬编码
    """

# 2. ExecutorNode —— 对应 FC-CodingWorkflow（你的场景是 search + tool calling）
def create_executor_node(deps, batch_size=5):
    """完全通用，只看 query_queue，不关心任务类型"""

# 3. SynthesizerNode —— 把 evidence 合并进 structured_view
def create_synthesizer_node(deps, task_profile: TaskProfile):
    """
    用 task_profile.output_schema 决定结构化输出类型
    merge 逻辑通过 task_profile 的 merge_fn 或 generic merge_view_update
    """

# 4. ReflectorNode —— 对应 FC-ReasoningPipeline + FC-EvaluationStrategy
def create_reflector_node(deps, task_profile: TaskProfile):
    """
    评估 structured_view 的覆盖度
    路由决策：exit / run_existing_queue / plan_more
    
    关键：routing_decision 写进 ExplorationGraph.current_node
    """

# 5. AssumptionProbeNode —— 可选，由 TaskProfile.enable_assumption_probe 控制
def create_assumption_probe_node(deps, task_profile: TaskProfile): ...

# 6. FinalizerNode —— 生成 final_report
def create_finalizer_node(deps, task_profile: TaskProfile):
    """prompt 模板 + task_profile.output_schema 决定报告格式"""
```

---

### Layer 5：GenericResearchSubgraph（通用图构建器）

```python
class GenericResearchSubgraph:
    def __init__(self, deps, task_profile: TaskProfile): 
        self.deps = deps
        self.tp = task_profile
    
    def build(self) -> StateGraph:
        graph = StateGraph(AgentState)
        
        # 通用节点，全部通过 task_profile 参数化
        graph.add_node("skill_selector", create_skill_selector_node(self.deps, self.tp))
        graph.add_node("initial_planner", create_planner_node(self.deps, self.tp, mode="initial"))
        graph.add_node("executor", create_executor_node(self.deps))
        graph.add_node("synthesizer", create_synthesizer_node(self.deps, self.tp))
        graph.add_node("reflector", create_reflector_node(self.deps, self.tp))
        graph.add_node("loop_planner", create_planner_node(self.deps, self.tp, mode="loop"))
        
        # 可选节点，由 TaskProfile 控制
        if self.tp.enable_assumption_probe:
            graph.add_node("assumption_probe", create_assumption_probe_node(self.deps, self.tp))
        
        graph.add_node("finalizer", create_finalizer_node(self.deps, self.tp))
        graph.add_node("human_review", create_human_review_node(self.deps))
        
        # 边的拓扑结构是固定的 Plan→Execute→Reflect loop
        # 不依赖任务类型
        self._wire_edges(graph)
        return graph
    
    def _wire_edges(self, graph):
        # START → skill_selector → initial_planner → executor → synthesizer → reflector
        # reflector → (exit → assumption_probe → finalizer) | (continue → loop_planner → executor)
        ...
```

**关键洞察**：图的**拓扑结构**（哪些节点、怎么连线）是固定的通用框架；**节点行为**通过 `TaskProfile` 参数化。未来换一个研究阶段，只需要换 `TaskProfile`，不需要重写图。

---

## Consensus 的变化：从子图变成 TaskProfile 实例

```python
# 之前
ConsensusSubgraph(deps).build()  # 几百行专用代码

# 之后
CONSENSUS_TASK_PROFILE = TaskProfile(
    task_id="consensus",
    objective="Build market consensus view across analyst estimates",
    dimensions=CONSENSUS_DIMENSIONS,
    output_schema=StructuredConsensusView,
    default_queries_fn=_default_consensus_queries,
    coverage_threshold=0.75,
    max_iterations=5,
    skill_objective="consensus",
    enable_assumption_probe=True,
)

GenericResearchSubgraph(deps, CONSENSUS_TASK_PROFILE).build()
```

未来加 `FundamentalAnalysis`：

```python
FUNDAMENTAL_TASK_PROFILE = TaskProfile(
    task_id="fundamental",
    objective="Build fundamental analysis view covering revenue drivers, margins, moat",
    dimensions=FUNDAMENTAL_DIMENSIONS,
    output_schema=StructuredFundamentalView,
    ...
    enable_assumption_probe=False,
)

GenericResearchSubgraph(deps, FUNDAMENTAL_TASK_PROFILE).build()
```

**零重复代码**。

---


## 关于 R&D-Agent 论文的几个关键映射

| 论文概念 | 你的对应实现 |
|---|---|
| `R&D Loop` | `executor → synthesizer → reflector` 一次循环 |
| `SelectParents(G, π)` | `ReflectorNode` 路由 + `ExplorationGraph.select_parents()` |
| `Virtual Evaluation` | `ReflectorNode` 的 LLM 评分（coverage evaluation） |
| `Collaborative Memory` | `MemoryStore` 跨 branch 共享 search_memory |
| `Efficient Debug` | 你的 batch_executor 的 batch_size 控制 |
| `Aggregated Evaluation` | `ScorerNode` 对多 branch 的 `coverage_score` 排序，选最优 |

---

## 核心洞察：你已经有了95%的基础设施

你现有的 Skills/Tools 设计已经非常成熟。真正缺的是**上层调度层**——一个能自主分解任务、把子任务分配给独立 loop 的 Orchestrator。好，现在把完整设计讲清楚。


1. **编排循环 (Orchestrator Loop)：** 最顶层的控制流。它接收用户请求，通过 **任务分解器 (Task Decomposer)** 将其拆解为详细的任务计划 (TaskPlan)。**分发器 (Dispatcher)** 将这些任务作为“子循环”发送给下游执行，最后由 **聚合器 (Aggregator)** 汇总所有结果。
2. **通用研究子图 (GenericResearchSubgraph)：** 核心的任务执行层，参数化运行。
* 它首先由 **技能选择器 (Skill Selector)** 和 **初始规划器 (Initial Planner)** 进行规划。
* 进入主要的 **执行器 (Executor)** 循环，执行器批量调用工具并收集证据，这些证据被记录在 **探索图 (Exploration Graph)** 中。
* **合成器 (Synthesizer)** 将证据整理成结构化视图，**反射器 (Reflector)** 进行评估。如果需要更多信息，它会通过 **循环规划器 (Loop Planner)** 扩展查询队列（loop / plan_more）；如果可以结束，则流向 **假设探针 (Assumption Probe)** 和 **终结器 (Finalizer)** 生成最终报告。
* 架构还包含了 **人工审查 (Human Review)** 环节，允许人工中断并要求重新规划（replan）。


3. **共享基础设施 (Shared Infrastructure)：** 无状态的注册表和存储，为所有子循环提供支持。包括 **技能注册表 (SkillRegistry)**、**工具注册表 (ToolRegistry)**、**内存存储 (MemoryStore)**、以及存储当前代理状态和探索图数据的实体。

这是一个复杂的系统，通过清晰的规划、执行、反射和聚合循环，利用 LLM 和各种工具来解决研究型任务。



---

## 整体思路：三层结构

图里已经表达了骨架，下面逐层讲设计决策。

---

### Layer 1：Orchestrator Loop

这是"自主分配子任务"的核心。它做三件事：

**Task Decomposer** 接收顶层研究目标（比如 `"equity research on NVDA"`），调用 LLM 输出一个 `TaskPlan`：

```python
@dataclass
class SubTaskSpec:
    task_id: str           # 从 TaskRegistry 取，如 "consensus"
    priority: int          # 执行顺序
    depends_on: list[str]  # 依赖哪些其他 sub_task 的结果（空 = 可立即执行）
    context_keys: list[str] # 需要从父 state 注入哪些字段
    override_config: dict  # 覆盖 TaskProfile 的部分参数

@dataclass  
class TaskPlan:
    sub_tasks: list[SubTaskSpec]
    parallel_groups: list[list[str]]  # 哪些可以并行
    rationale: str
```

LLM 只能从 **TaskRegistry 注册表**里选 task_id，这就是"半动态"的边界——它自主决定选哪些、顺序、依赖关系，但不能凭空创造新任务类型。

**Dispatcher** 按 `TaskPlan` 实例化 `GenericResearchSubgraph`，按 `parallel_groups` 决定串行还是并发调用。

**Aggregator** 收集所有子 loop 的 `final_report` 和 `structured_view`，合并成父级 state。

---

### Layer 2：GenericResearchSubgraph（完全复用）

这层的设计关键是**节点行为由 TaskProfile 参数化，拓扑结构固定不变**。

每个节点的 prompt 构建都从 TaskProfile 读取：

```python
@dataclass
class TaskProfile:
    task_id: str
    objective: str
    
    # Skill 控制
    skill_objective: str          # 传给 SkillRegistry.select_for_objective()
    agent_visibility_id: str      # 对应 agent_visibility.py 里的 key
    max_skills: int = 2
    
    # Planner 控制
    dimensions: list[str]         # 需要覆盖的研究维度
    default_queries_fn: callable  # 冷启动 fallback
    max_initial_queries: int = 5
    max_loop_queries: int = 2
    
    # Synthesizer 控制
    output_schema: type           # Pydantic model
    merge_strategy: str = "incremental"  # 或 "replace"
    
    # Reflector 控制
    coverage_threshold: float = 0.75
    max_iterations: int = 5
    
    # 可选节点开关
    enable_assumption_probe: bool = False
    enable_human_review: bool = False
    
    # Finalizer 控制
    report_format: str = "markdown"
    report_max_chars: int = 6000
```

所有节点工厂签名统一为：

```python
def create_planner_node(deps, task_profile: TaskProfile, mode: str):
    def planner(state: AgentState) -> dict:
        # 从 task_profile.dimensions 构建 prompt
        # 从 task_profile.default_queries_fn 获取 fallback
        ...
    return planner
```

---

### Layer 3：Shared Infrastructure（零修改，按现有设计复用）

你现有的 `SkillRegistry`、`ToolRegistry`、`MemoryStore` 完全不动，只是调用方式统一化：

Skill 的注入路径和你现有的完全一致：

```
scan_catalog() → visibility filter (by agent_visibility_id) 
→ LLM select via load_research_skills tool 
→ read_skill() full body 
→ build_skill_context() → active_skill_context in AgentState
```

唯一变化是 `agent_visibility_id` 从硬编码的 `"consensus_subgraph"` 变成从 `TaskProfile` 读取。

---

## 目录结构

```
tradingagents/equity_research/
│
├── runtime/                         # 新增，纯框架，零业务逻辑
│   ├── state.py                     # AgentState (TypedDict, 通用字段)
│   ├── task_profile.py              # TaskProfile dataclass
│   ├── task_registry.py             # TaskRegistry: 注册 + 查找 TaskProfile
│   ├── task_plan.py                 # SubTaskSpec, TaskPlan
│   ├── exploration_graph.py         # ExplorationGraph, ExplorationNode
│   │
│   ├── orchestrator/
│   │   ├── nodes.py                 # decomposer, dispatcher, aggregator
│   │   ├── routers.py
│   │   └── graph.py                 # OrchestratorGraph.build()
│   │
│   ├── nodes/                       # 六个通用节点，全部参数化
│   │   ├── skill_selector.py
│   │   ├── planner.py               # create_planner_node(mode="initial|loop")
│   │   ├── executor.py              # create_executor_node (batch tool calls)
│   │   ├── synthesizer.py           # create_synthesizer_node
│   │   ├── reflector.py             # create_reflector_node
│   │   ├── assumption_probe.py      # create_assumption_probe_node
│   │   ├── finalizer.py             # create_finalizer_node
│   │   └── human_review.py
│   │
│   ├── routers.py                   # 通用路由函数 (coverage_router, etc.)
│   └── subgraph.py                  # GenericResearchSubgraph.build(task_profile)
│
├── tasks/                           # 纯业务配置，只有数据，无框架代码
│   ├── registry.py                  # 注册所有 TaskProfile → TaskRegistry
│   ├── consensus/
│   │   ├── profile.py               # CONSENSUS_PROFILE = TaskProfile(...)
│   │   ├── schemas.py               # StructuredConsensusView (保持不变)
│   │   └── queries.py               # _default_consensus_queries()
│   ├── fundamental/
│   │   ├── profile.py
│   │   ├── schemas.py
│   │   └── queries.py
│   ├── risk/
│   └── valuation/
│
├── skills/                          # 完全不动
├── tools/                           # 完全不动
└── agents/
    └── shared/                      # 保留现有 shared 工具，逐步迁移
```

---

## Orchestrator 的核心 Prompt 设计

Task Decomposer 的 prompt 模板，体现"半动态"的约束：

```python
def _decomposer_prompt(state: AgentState, registry: TaskRegistry) -> str:
    catalog = registry.format_catalog()  # 类似 SkillRegistry 的 catalog table
    return f"""
You are an equity research orchestrator for {state['ticker']}.
Sector: {state.get('sector', '')}
Research objective: {state.get('research_objective', 'comprehensive equity research')}

Available research task types (you may only select from this list):
{catalog}

Decompose the research objective into 2-5 sub-tasks.
For each sub-task, specify:
- task_id: must be from the catalog above
- priority: integer (lower = higher priority)  
- depends_on: list of task_ids that must complete first ([] = run immediately)
- context_keys: which fields from completed tasks to pass in
  (e.g. ["consensus_view", "fundamental_view"])

Return JSON only. Example:
{{
  "sub_tasks": [
    {{"task_id": "consensus", "priority": 1, "depends_on": [], "context_keys": []}},
    {{"task_id": "fundamental", "priority": 2, "depends_on": [], "context_keys": []}},
    {{"task_id": "valuation", "priority": 3, 
      "depends_on": ["consensus", "fundamental"],
      "context_keys": ["consensus_view", "fundamental_view"]}}
  ],
  "rationale": "..."
}}
"""
```

TaskRegistry 的 catalog 格式和你现有的 SkillRegistry catalog 完全一致，LLM 已经会用这个模式了。

---

## AgentState 设计（关键解耦点）

```python
class AgentState(TypedDict):
    # 任务描述
    task_profile: dict          # TaskProfile.to_dict()
    ticker: str
    sector: str
    research_objective: str
    
    # 探索图
    exploration_graph: dict     # ExplorationGraph 序列化
    current_node_id: str
    
    # Skill 上下文（SkillRegistry 写入，节点读取）
    active_skill_context: dict
    
    # Plan-Execute-Reflect 流转字段
    query_queue: list[dict]     # QueryItem list
    pending_evidence: list[dict]
    search_memory: list[dict]   # 全量历史
    
    # 结构化输出（类型由 task_profile.output_schema 决定）
    structured_view: dict       # consensus → StructuredConsensusView.dump()
                                # fundamental → StructuredFundamentalView.dump()
    coverage_report: dict
    coverage_history: list[dict]
    
    # 可选
    assumptions: dict           # 仅 enable_assumption_probe=True 时写入
    
    # 产物
    final_report: str
    
    # 系统字段
    iterations: int
    max_iterations: int
    api_calls: int
    documents: list[dict]
    errors: list[str]
    compliance_flags: list[dict]
    human_review_payload: dict
    last_updated: str
    
    # Orchestrator 注入的跨任务上下文
    parent_context: dict        # 来自 depends_on 任务的 structured_view 等
```

`consensus_view`、`consensus_report`、`consensus_*` 全部消失，统一成 `structured_view` 和 `final_report`。

---

## 迁移路径（三个阶段，每个阶段独立可测）

**Phase 1 — State 清洗**（不改行为，只重命名字段）

把 `ConsensusSubgraphState` 里的 `consensus_*` 字段映射到 `AgentState` 的通用字段。保持 `ConsensusSubgraph` 外壳不变，内部节点读写新字段名。

**Phase 2 — 节点通用化**（抽取 `runtime/nodes/`）

从 `consensus/nodes.py` 中把每个节点工厂提取到 `runtime/nodes/`，原来硬编码的 consensus 维度、schema、prompt 片段全部改成从 `task_profile` 读取。

consensus 成为第一个 `TaskProfile` 实例，`GenericResearchSubgraph(deps, CONSENSUS_PROFILE).build()` 替代 `ConsensusSubgraph(deps).build()`，行为完全一致。

**Phase 3 — Orchestrator 上线**

在 `runtime/orchestrator/` 实现 Decomposer + Dispatcher + Aggregator，`TaskRegistry` 注册 consensus 等已有 profile，Orchestrator 开始自主分配。

三个阶段之间有清晰的接口边界，Phase 2 完成后就可以开始添加新的 `TaskProfile`（fundamental、risk 等），不需要等 Phase 3。

