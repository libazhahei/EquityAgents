> 英文版 | [TRADINGAGENTS.md](../TRADINGAGENTS.md)
> 股票研究文档 | [README.zh-CN.md](../../README.zh-CN.md)

---

> **本仓库根目录 [README.md](../../README.md) 记录的是股票研究（R&D-Agent）工作流。**
> 本页保留上游 TradingAgents 多智能体**交易框架**文档。
>
> English | [docs/TRADINGAGENTS.md](../TRADINGAGENTS.md)

---

<p align="center">
  <img src="../assets/TauricResearch.png" style="width: 60%; height: auto;">
</p>

<div align="center" style="line-height: 1;">
  <a href="https://arxiv.org/abs/2412.20138" target="_blank"><img alt="arXiv" src="https://img.shields.io/badge/arXiv-2412.20138-B31B1B?logo=arxiv"/></a>
  <a href="https://discord.com/invite/hk9PGKShPK" target="_blank"><img alt="Discord" src="https://img.shields.io/badge/Discord-TradingResearch-7289da?logo=discord&logoColor=white&color=7289da"/></a>
  <a href="../assets/wechat.png" target="_blank"><img alt="WeChat" src="https://img.shields.io/badge/WeChat-TauricResearch-brightgreen?logo=wechat&logoColor=white"/></a>
  <a href="https://x.com/TauricResearch" target="_blank"><img alt="X Follow" src="https://img.shields.io/badge/X-TauricResearch-white?logo=x&logoColor=white"/></a>
  <br>
  <a href="https://github.com/TauricResearch/" target="_blank"><img alt="Community" src="https://img.shields.io/badge/Join_GitHub_Community-TauricResearch-14C290?logo=discourse"/></a>
</div>

<div align="center">
  <!-- Keep these links. Translations will automatically update with the README. -->
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=de">Deutsch</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=es">Español</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=fr">français</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ja">日本語</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ko">한국어</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=pt">Português</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=ru">Русский</a> | 
  <a href="https://www.readme-i18n.com/TauricResearch/TradingAgents?lang=zh">中文</a>
</div>

---

# TradingAgents：多智能体 LLM 金融交易框架

## 新闻

- [2026-05] **TradingAgents v0.2.5** 发布：落地版情绪分析师、GPT-5.5 等模型覆盖、Qwen/GLM/MiniMax 双区域支持、`TRADINGAGENTS_*` 环境变量可配置与 API 密钥自动检测、远程 Ollama 支持、非美股 alpha 基准，以及 ticker 路径遍历加固。完整列表见 [CHANGELOG.md](../../CHANGELOG.md)。
- [2026-04] **TradingAgents v0.2.4** 发布：结构化输出智能体（研究经理、交易员、投资组合经理）、LangGraph 检查点恢复、持久化决策日志、DeepSeek/Qwen/GLM/Azure 提供商支持、Docker，以及 Windows UTF-8 编码修复。
- [2026-03] **TradingAgents v0.2.3** 发布：多语言支持、GPT-5.4 系列模型、统一模型目录、回测日期保真度，以及代理支持。
- [2026-03] **TradingAgents v0.2.2** 发布：GPT-5.4/Gemini 3.1/Claude 4.6 模型覆盖、五级评级量表、OpenAI Responses API、Anthropic effort 控制，以及跨平台稳定性。
- [2026-02] **TradingAgents v0.2.0** 发布：多提供商 LLM 支持（GPT-5.x、Gemini 3.x、Claude 4.x、Grok 4.x）与改进的系统架构。
- [2026-01] **Trading-R1** [技术报告](https://arxiv.org/abs/2509.11420) 发布，[Terminal](https://github.com/TauricResearch/Trading-R1) 预计即将上线。

<div align="center">
<a href="https://www.star-history.com/#TauricResearch/TradingAgents&Date">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" />
   <img alt="TradingAgents Star History" src="https://api.star-history.com/svg?repos=TauricResearch/TradingAgents&type=Date" style="width: 80%; height: auto;" />
 </picture>
</a>
</div>

> 🎉 **TradingAgents** 正式发布！我们收到了大量关于本工作的咨询，感谢社区的热情支持。
>
> 因此我们决定完全开源该框架。期待与你一起构建有影响力的项目！

<div align="center">

🚀 [TradingAgents 框架](#tradingagents-框架) | ⚡ [安装与 CLI](#安装与-cli) | 🎬 [演示](https://www.youtube.com/watch?v=90gr5lwjIho) | 📦 [包用法](#tradingagents-包) | 🤝 [贡献](#贡献) | 📄 [引用](#引用)

</div>

## TradingAgents 框架

TradingAgents 是一个多智能体交易框架，模拟真实交易公司的运作方式。通过部署专业化的 LLM 智能体——从基本面分析师、情绪专家、技术分析师，到交易员、风险管理团队——平台协同评估市场状况并辅助交易决策。此外，这些智能体会通过动态讨论来确定最优策略。

<p align="center">
  <img src="../assets/schema.png" style="width: 100%; height: auto;">
</p>

> TradingAgents 框架仅供研究用途。交易表现可能因多种因素而异，包括所选骨干语言模型、模型温度、交易周期、数据质量及其他非确定性因素。[不构成财务、投资或交易建议。](https://tauric.ai/disclaimer/)

我们的框架将复杂的交易任务分解为专业化角色。

### 分析师团队

- **基本面分析师**：评估公司财务与业绩指标，识别内在价值与潜在风险信号。
- **情绪分析师**：聚合新闻标题、StockTwits 与 Reddit 讨论，形成单一情绪读数，衡量短期市场情绪。
- **新闻分析师**：监控全球新闻与宏观经济指标，解读事件对市场状况的影响。
- **技术分析师**：运用技术指标（如 MACD、RSI）识别交易形态并预测价格走势。

<p align="center">
  <img src="../assets/analyst.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

### 研究团队

- 由看涨与看跌研究员组成，批判性评估分析师团队的洞见。通过结构化辩论，在潜在收益与固有风险之间取得平衡。

<p align="center">
  <img src="../assets/researcher.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### 交易员智能体

- 综合分析师与研究员的报告做出交易决策，确定交易时机与规模。

<p align="center">
  <img src="../assets/trader.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

### 风险管理与投资组合经理

- 持续评估投资组合风险，考量市场波动、流动性及其他风险因素。风险管理团队评估并调整交易策略，向投资组合经理提供评估报告以供最终决策。
- 投资组合经理批准或拒绝交易提案。若获批准，订单将发送至模拟交易所并执行。

<p align="center">
  <img src="../assets/risk.png" width="70%" style="display: inline-block; margin: 0 2%;">
</p>

## 安装与 CLI

### 安装

克隆 TradingAgents：

```bash
git clone https://github.com/TauricResearch/TradingAgents.git
cd TradingAgents
```

在你喜欢的环境管理器中创建虚拟环境：

```bash
conda create -n tradingagents python=3.12
conda activate tradingagents
```

安装包及其依赖：

```bash
pip install .
```

### Docker

也可使用 Docker 运行：

```bash
cp .env.example .env  # add your API keys
docker compose run --rm tradingagents
```

本地模型（Ollama）：

```bash
docker compose --profile ollama run --rm tradingagents-ollama
```

### 所需 API

TradingAgents 支持多种 LLM 提供商。为所选提供商设置 API 密钥：

```bash
export OPENAI_API_KEY=...          # OpenAI (GPT)
export GOOGLE_API_KEY=...          # Google (Gemini)
export ANTHROPIC_API_KEY=...       # Anthropic (Claude)
export XAI_API_KEY=...             # xAI (Grok)
export DEEPSEEK_API_KEY=...        # DeepSeek
export DASHSCOPE_API_KEY=...       # Qwen — International (dashscope-intl.aliyuncs.com)
export DASHSCOPE_CN_API_KEY=...    # Qwen — China (dashscope.aliyuncs.com)
export ZHIPU_API_KEY=...           # GLM via Z.AI (international)
export ZHIPU_CN_API_KEY=...        # GLM via BigModel (China, open.bigmodel.cn)
export MINIMAX_API_KEY=...         # MiniMax — Global (api.minimax.io)
export MINIMAX_CN_API_KEY=...      # MiniMax — China (api.minimaxi.com)
export OPENROUTER_API_KEY=...      # OpenRouter
export ALPHA_VANTAGE_API_KEY=...   # Alpha Vantage
```

Azure OpenAI：将 `.env.enterprise.example` 复制为 `.env.enterprise` 并填写凭据。

AWS Bedrock：使用 `pip install ".[bedrock]"` 安装扩展，设置 `llm_provider: "bedrock"`，配置 AWS 凭据（环境变量、`~/.aws/credentials` 或 IAM 角色）与 `AWS_DEFAULT_REGION`，并使用 Bedrock 模型 ID，例如 `us.anthropic.claude-opus-4-8-v1:0`。

本地模型：使用 `llm_provider: "ollama"` 配置 Ollama。默认端点为 `http://localhost:11434/v1`；设置 `OLLAMA_BASE_URL` 指向远程 `ollama-serve`。使用 `ollama pull <name>` 拉取模型，CLI 中对未默认列出的模型选择「Custom model ID」。

其他 OpenAI 兼容服务器（vLLM、LM Studio、llama.cpp 或自定义中继）：使用 `llm_provider: "openai_compatible"`，通过 `backend_url`（或 `TRADINGAGENTS_LLM_BACKEND_URL`）设置端点，例如 vLLM 为 `http://localhost:8000/v1`，LM Studio 为 `http://localhost:1234/v1`。模型由你的服务器提供。本地服务器通常无需密钥；端点需要时设置 `OPENAI_COMPATIBLE_API_KEY`。

也可将 `.env.example` 复制为 `.env` 并填写密钥：

```bash
cp .env.example .env
```

### CLI 用法

启动交互式 CLI：

```bash
tradingagents          # installed command
python -m cli.main     # alternative: run directly from source
```

你将看到可选择标的、分析日期、LLM 提供商、研究深度等选项的界面。

### 市场与标的

TradingAgents 支持 Yahoo Finance 覆盖的任意市场，使用带交易所后缀的 ticker。公司身份与 alpha 基准按市场自动解析。

- 美国：`AAPL`、`SPY`
- 香港：`0700.HK` · 东京：`7203.T` · 伦敦：`AZN.L`
- 印度：`RELIANCE.NS`、`.BO` · 加拿大：`.TO` · 澳大利亚：`.AX`
- 中国 A 股：上海 `.SS`、深圳 `.SZ`（如贵州茅台 `600519.SS`）
- 加密货币：`BTC-USD`、`ETH-USD`

<p align="center">
  <img src="../assets/cli/cli_init.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

界面会随结果加载而更新，便于跟踪智能体运行进度。

<p align="center">
  <img src="../assets/cli/cli_news.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

<p align="center">
  <img src="../assets/cli/cli_transaction.png" width="100%" style="display: inline-block; margin: 0 2%;">
</p>

## TradingAgents 包

### 实现细节

我们使用 LangGraph 构建 TradingAgents，以确保灵活性与模块化。框架支持多种 LLM 提供商：OpenAI、Google、Anthropic、xAI、DeepSeek、Qwen（阿里云 DashScope，国际与中国端点）、GLM（智谱）、MiniMax（全球 + 中国）、OpenRouter、Ollama 本地模型，以及企业级 Azure OpenAI。

### Python 用法

在代码中使用 TradingAgents 时，可导入 `tradingagents` 模块并初始化 `TradingAgentsGraph()` 对象。`.propagate()` 函数将返回决策。可运行 `main.py`，也可参考以下示例：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

ta = TradingAgentsGraph(debug=True, config=DEFAULT_CONFIG.copy())

# forward propagate
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

也可调整默认配置，设置 LLM、辩论轮次等：

```python
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"        # e.g. openai, google, anthropic, deepseek, groq, ollama; openai_compatible covers any OpenAI-compatible endpoint (vLLM, LM Studio, llama.cpp, ...)
config["deep_think_llm"] = "gpt-5.5"     # Model for complex reasoning
config["quick_think_llm"] = "gpt-5.4-mini" # Model for quick tasks
config["max_debate_rounds"] = 2

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
print(decision)
```

所有配置选项见 `tradingagents/default_config.py`。

## 持久化与恢复

TradingAgents 在多次运行间持久化两类状态。

### 决策日志

决策日志始终开启。每次完成的运行会将其决策追加到 `~/.tradingagents/memory/trading_memory.md`。下次对同一 ticker 运行时，TradingAgents 会获取已实现收益（原始收益与相对 SPY 的 alpha），生成一段反思，并将最近同 ticker 决策与近期跨 ticker 教训注入投资组合经理 prompt，使每次分析能延续过往经验。

使用 `TRADINGAGENTS_MEMORY_LOG_PATH` 覆盖路径。

### 检查点恢复

检查点恢复通过 `--checkpoint` 可选开启。启用后，LangGraph 在每个节点后保存状态，崩溃或中断的运行可从最后成功步骤恢复，而非从头开始。恢复运行时日志会显示 `Resuming from step N for <TICKER> on <date>`；新运行显示 `Starting fresh`。成功完成后检查点自动清除。

每个 ticker 的 SQLite 数据库位于 `~/.tradingagents/cache/checkpoints/<TICKER>.db`（使用 `TRADINGAGENTS_CACHE_DIR` 覆盖基目录）。运行前使用 `--clear-checkpoints` 重置全部检查点。

```bash
tradingagents analyze --checkpoint           # enable for this run
tradingagents analyze --clear-checkpoints    # reset before running
```

```python
config = DEFAULT_CONFIG.copy()
config["checkpoint_enabled"] = True
ta = TradingAgentsGraph(config=config)
_, decision = ta.propagate("NVDA", "2026-01-15")
```

## 可复现性

TradingAgents 由 LLM 驱动，同一 ticker 与日期的两次运行可能不同。对于基于语言模型的研究工具而言这是预期行为，并非缺陷。差异来自几个不同来源，区分它们有助于理解。

语言模型采样是非确定性的。即使温度固定，提供商也不保证跨次调用输出字节级一致；推理模型（默认 GPT-5.x 系列及任何思考模式模型）变化最大，因为其内部推理本身也在采样。

实时数据会变动。新闻、StockTwits 与 Reddit 随时间返回不同内容，因此今天的运行与上周对同一历史交易日期的运行会看到不同输入。固定分析日期可锁定价格与指标窗口，但社交与新闻源仍反映「当前」。

要减少差异，可降低采样温度。在配置中设置 `temperature`（或 `.env` 中的 `TRADINGAGENTS_TEMPERATURE`）；较低值使遵守温度的模型更可重复。推理模型基本忽略温度，因此若要更紧的可复现性，可将低温度与非推理模型（如 `gpt-4.1`）搭配使用。

```python
config = DEFAULT_CONFIG.copy()
config["llm_provider"] = "openai"
config["deep_think_llm"] = "gpt-4.1"      # non-reasoning model honors temperature
config["quick_think_llm"] = "gpt-4.1"
config["temperature"] = 0.0
```

以下已不再变化：被分析公司身份在任何智能体运行前由 ticker 确定性解析；市场分析师将精确价格与指标声明锚定在已验证数据快照上。早期报告中「不同公司」或跨运行虚构价格水平的问题，已由上述两项机制解决。

回测结果不保证与任何已发表数字一致。收益取决于模型、温度、日期范围、数据质量及上述采样。请将框架视为研究多智能体分析的脚手架，而非具有固定、可复现收益的策略。

## 贡献

欢迎贡献：缺陷修复、文档与功能建议；过往贡献按版本记入 [`CHANGELOG.md`](../../CHANGELOG.md)。

## 引用

若 *TradingAgents* 对你有所帮助，请引用我们的工作 :)

```
@misc{xiao2025tradingagentsmultiagentsllmfinancial,
      title={TradingAgents: Multi-Agents LLM Financial Trading Framework}, 
      author={Yijia Xiao and Edward Sun and Di Luo and Wei Wang},
      year={2025},
      eprint={2412.20138},
      archivePrefix={arXiv},
      primaryClass={q-fin.TR},
      url={https://arxiv.org/abs/2412.20138}, 
}
```
