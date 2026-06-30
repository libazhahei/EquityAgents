"""Perplexity client — LangChain/LangGraph/LangSmith 兼容版本。

三条路径：
1. Chat (Sonar)      → ChatPerplexity (langchain-perplexity) 或 ChatOpenAI + base_url
2. Search API        → PerplexitySearchResults tool (LangChain tool，可直接挂到 agent)
3. Agent API (新)    → openai.OpenAI(base_url=.../v1) 调用 client.responses.create()

所有调用均走 OpenAI-compatible SDK，不再直接使用 httpx/curl。
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from enum import Enum
from typing import Any

# ---------- LangChain 原生集成（推荐） ----------
# pip install langchain-perplexity
from langchain_perplexity import ChatPerplexity, PerplexitySearchResults

# ---------- 通用 OpenAI SDK（Chat 备用 / Agent API） ----------
# pip install openai
from openai import OpenAI

# ---------- LangChain 核心 ----------
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from .api_key_env import get_api_key_env
from .base_client import BaseLLMClient
from .validators import validate_model

logger = logging.getLogger(__name__)

# ── 端点常量 ────────────────────────────────────────────────────────────────
# Sonar / Chat 端点（/chat/completions，OpenAI SDK 兼容）
PERPLEXITY_SONAR_BASE_URL = "https://api.perplexity.ai"

# Agent API 端点（/v1/agent 或 /v1/responses，OpenAI Responses API 兼容）
PERPLEXITY_AGENT_BASE_URL = "https://api.perplexity.ai/v1"

DEFAULT_MODEL = "sonar-pro"

KNOWN_SONAR_MODELS = (
    "sonar",
    "sonar-pro",
    "sonar-deep-research",
    "sonar-reasoning-pro",
)

_PASSTHROUGH_KWARGS = (
    "timeout",
    "max_retries",
    "temperature",
    "api_key",
    "callbacks",
)


class SearchMode(str, Enum):
    EXPLORATORY = "exploratory"
    TARGETED = "targeted"
    CONTRADICTION = "contradiction"


_SYSTEM_PROMPTS = {
    SearchMode.EXPLORATORY: (
        "You are an equity research assistant. Provide factual, cited information "
        "about companies and industries. Focus on publicly verifiable facts."
    ),
    SearchMode.TARGETED: (
        "You are an evidence retrieval assistant. Find specific, citable evidence "
        "that supports or refutes an investment hypothesis. Cite primary sources."
    ),
    SearchMode.CONTRADICTION: (
        "You are a devil's advocate researcher. Find counter-evidence, risks, and "
        "bear cases for the given thesis. Cite credible sources."
    ),
}


class PerplexityClient(BaseLLMClient):
    """TradingAgents client — LangChain / LangGraph / LangSmith 兼容。

    get_llm()   → ChatPerplexity（langchain-perplexity 原生，可直接传入 create_react_agent）
    search()    → PerplexitySearchResults tool（LangChain BaseTool，可挂到任何 agent）
    agent()     → Perplexity Agent API，通过 openai SDK 的 client.responses.create()
    """

    provider = "perplexity"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str | None = None,
        *,
        config: dict[str, Any] | None = None,
        rate_limiter: Callable[[], bool] | None = None,
        **kwargs: Any,
    ):
        super().__init__(model, base_url or PERPLEXITY_SONAR_BASE_URL, **kwargs)
        self.config = config or {}
        self._api_key_override = kwargs.get("api_key")
        self._rate_limiter = rate_limiter

    # ── 工厂方法 ─────────────────────────────────────────────────────────────

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        rate_limiter: Callable[[], bool] | None = None,
    ) -> "PerplexityClient":
        er = config.get("equity_research", {})
        return cls(
            model=er.get("perplexity_model", DEFAULT_MODEL),
            base_url=config.get("perplexity_base_url"),
            config=config,
            rate_limiter=rate_limiter,
        )

    # ── API key ──────────────────────────────────────────────────────────────

    @property
    def api_key(self) -> str:
        if self._api_key_override:
            return str(self._api_key_override)
        return (
            self.config.get("perplexity_api_key")
            or os.environ.get(
                get_api_key_env("perplexity") or "PERPLEXITY_API_KEY", ""
            )
        )

    def _require_api_key(self) -> str:
        if not self.api_key:
            env_var = get_api_key_env("perplexity") or "PERPLEXITY_API_KEY"
            raise ValueError(
                f"API key for provider 'perplexity' is not set. "
                f"Please set {env_var} (e.g. add {env_var}=your_key to your .env file)."
            )
        return self.api_key

    # ── 1. Chat LLM — LangChain 原生 ChatPerplexity ─────────────────────────

    def get_llm(
        self,
        *,
        search_domain_filter: list[str] | None = None,
    ) -> ChatPerplexity:
        """返回 ChatPerplexity 实例。

        该实例与 LangChain / LangGraph 完全兼容：
        - 可直接传入 create_react_agent(model, tools)
        - 支持 LangSmith tracing（只需设置 LANGSMITH_API_KEY 环境变量）
        - 支持 .stream() / .ainvoke() / .batch()

        示例::

            from langgraph.prebuilt import create_react_agent
            agent = create_react_agent(client.get_llm(), tools=[client.get_search_tool()])
        """
        self._require_api_key()
        self.warn_if_unknown_model()

        kwargs: dict[str, Any] = {
            "model": self.model,
            "pplx_api_key": self.api_key,
        }
        if search_domain_filter:
            kwargs["search_domain_filter"] = search_domain_filter
        for key in _PASSTHROUGH_KWARGS:
            if key in self.kwargs and key not in ("api_key",):
                kwargs[key] = self.kwargs[key]

        return ChatPerplexity(**kwargs)

    # ── 2. Search Tool — LangChain BaseTool ──────────────────────────────────

    def get_search_tool(self, *, k: int = 5) -> BaseTool:
        """返回 PerplexitySearchResults，一个标准 LangChain tool。

        可直接传入任何需要 tools: list[BaseTool] 的地方：

        示例::

            agent = create_react_agent(llm, [client.get_search_tool()])
            result = agent.invoke({"messages": [("user", "NVDA latest earnings?")]})
        """
        self._require_api_key()
        return PerplexitySearchResults(
            api_key=self.api_key,
            k=k,
        )

    # ── 3. Agent API — openai SDK → /v1/responses ────────────────────────────

    def _get_openai_client(self) -> OpenAI:
        """返回指向 Perplexity Agent API 的 OpenAI SDK 客户端。

        Agent API 与 OpenAI Responses API 接口一致，
        OpenAI SDK 会把 client.responses.create() 路由到 /v1/responses，
        Perplexity 同时接受 /v1/agent 和 /v1/responses。
        """
        return OpenAI(
            api_key=self._require_api_key(),
            base_url=PERPLEXITY_AGENT_BASE_URL,
        )

    def agent(
        self,
        query: str,
        *,
        model: str = "openai/gpt-4o-mini",   # Agent API 支持第三方模型
        preset: str | None = None,             # 例如 "pro-search"
        stream: bool = False,
        **extra: Any,
    ) -> dict[str, Any]:
        """通过 Perplexity Agent API 执行带 web search 的查询。

        Agent API 自动进行 web search + 多步推理，无需手动拼 system prompt。
        返回结构化字典，包含 answer 和 citations。

        参数:
            query:  用户查询。
            model:  Agent API 模型字符串，如 "openai/gpt-4o"、"openai/gpt-5.5"。
                    也可使用 preset 代替 model。
            preset: Perplexity 预设，如 "pro-search"（会覆盖 model）。
            stream: 是否流式输出（仅打印，不影响返回值）。

        示例::

            result = client.agent("NVDA Q1 2025 earnings highlights")
            print(result["answer"])
            print(result["citations"])
        """
        if self._rate_limiter and not self._rate_limiter():
            logger.warning("Perplexity rate limit exceeded")
            return {**self._empty_result(query, SearchMode.EXPLORATORY), "rate_limited": True}

        openai_client = self._get_openai_client()

        # preset 通过 extra_body 传递（OpenAI SDK 扩展参数）
        create_kwargs: dict[str, Any] = {
            "input": query,
            "stream": stream,
            **extra,
        }
        if preset:
            create_kwargs["extra_body"] = {"preset": preset}
        else:
            create_kwargs["model"] = model

        try:
            response = openai_client.responses.create(**create_kwargs)

            if stream:
                # 流式打印并手动收集文本
                collected: list[str] = []
                for event in response:
                    if event.type == "response.output_text.delta":
                        print(event.delta, end="", flush=True)
                        collected.append(event.delta)
                print()
                answer = "".join(collected)
                return {"answer": answer, "citations": [], "query": query, "mode": "agent"}

            # 从 output 中提取文本和 search_results
            answer_text = ""
            citations: list[str] = []
            for block in response.output:
                if getattr(block, "type", None) == "message":
                    for content_block in block.content:
                        if getattr(content_block, "type", None) == "output_text":
                            answer_text = content_block.text
                elif getattr(block, "type", None) == "search_results":
                    citations = [r.get("url", "") for r in (block.results or []) if r.get("url")]

            return {
                "answer": answer_text,
                "citations": citations,
                "query": query,
                "mode": "agent",
                "response_id": response.id,
                "usage": getattr(response, "usage", None),
            }

        except Exception as exc:
            logger.warning("Perplexity Agent API failed: %s", exc)
            return {**self._empty_result(query, SearchMode.EXPLORATORY), "error": str(exc)}

    # ── 4. chat_search — 使用 ChatPerplexity（LangChain 原生，带 LangSmith trace） ──

    def chat_search(
        self,
        query: str,
        *,
        mode: SearchMode = SearchMode.EXPLORATORY,
        search_domain_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """通过 ChatPerplexity 进行 grounded 搜索（自动记录 LangSmith trace）。

        与旧版的区别：使用 langchain-perplexity 的 ChatPerplexity
        而非 NormalizedChatOpenAI，与 LangGraph / LangSmith 原生兼容。
        """
        if not self.api_key:
            logger.warning("PERPLEXITY_API_KEY not set; returning empty result")
            return self._empty_result(query, mode)

        try:
            llm = self.get_llm(search_domain_filter=search_domain_filter)
            response = llm.invoke([
                SystemMessage(content=_SYSTEM_PROMPTS[mode]),
                HumanMessage(content=query),
            ])
            citations = response.additional_kwargs.get("citations", [])
            if not citations and hasattr(response, "response_metadata"):
                citations = response.response_metadata.get("citations", [])
            return {
                "answer": response.content,
                "citations": citations,
                "query": query,
                "mode": mode.value,
            }
        except Exception as exc:
            logger.warning("Perplexity chat_search failed: %s", exc)
            return {**self._empty_result(query, mode), "error": str(exc)}

    # ── 旧版 search() — 现在委托给 chat_search（保持向后兼容） ──────────────

    def search(
        self,
        query: str,
        mode: SearchMode = SearchMode.EXPLORATORY,
        *,
        max_results: int = 5,  # noqa: ARG002  保留参数签名兼容性
        search_domain_filter: list[str] | None = None,
    ) -> dict[str, Any]:
        """向后兼容的 search 方法，内部委托给 chat_search。

        原来直接调用 POST /search（非 OpenAI 兼容端点），
        现在统一走 ChatPerplexity，避免裸 httpx 请求。
        如果你需要真正的 Search API（返回 ranked snippets），
        请改用 get_search_tool() 返回的 LangChain tool。
        """
        if self._rate_limiter and not self._rate_limiter():
            logger.warning("Perplexity rate limit exceeded")
            result = self._empty_result(query, mode)
            result["rate_limited"] = True
            return result

        return self.chat_search(
            query,
            mode=mode,
            search_domain_filter=search_domain_filter,
        )

    # ── 金融验证（保持不变） ─────────────────────────────────────────────────

    def finance_verify(self, ticker: str, claim: str) -> dict[str, Any]:
        query = f"Verify this financial claim about {ticker}: {claim}"
        return self.chat_search(query, mode=SearchMode.TARGETED)

    # ── 验证 ─────────────────────────────────────────────────────────────────

    def validate_model(self) -> bool:
        return validate_model("perplexity", self.model)

    # ── 辅助 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _empty_result(query: str, mode: SearchMode) -> dict[str, Any]:
        return {"answer": "", "citations": [], "query": query, "mode": mode.value}


# ── 辅助函数（与原代码保持一致） ─────────────────────────────────────────────

def generate_search_plan(
    ticker: str,
    hypothesis: dict[str, Any],
    mode: SearchMode,
    max_queries: int,
) -> list[dict[str, str]]:
    hid = hypothesis.get("hypothesis_id", "")
    if mode == SearchMode.EXPLORATORY:
        queries = [
            f"{ticker} business model key revenue drivers",
            f"{ticker} industry competitive landscape market share",
            f"{ticker} recent earnings management guidance",
        ]
    elif mode == SearchMode.TARGETED:
        queries = [f"{ticker} {et}" for et in hypothesis.get("required_evidence", [])]
        if not queries:
            queries = [f"{ticker} {hypothesis.get('statement', '')}"]
    else:
        queries = [
            f"{ticker} challenges risks downside",
            f"{ticker} competitive threat bear case",
        ]
    return [
        {"query": q, "hypothesis_id": hid, "mode": mode.value}
        for q in queries[:max_queries]
    ]



"""perplexity_examples.py — 使用示例

安装依赖：
    pip install langchain-perplexity langgraph openai langsmith

环境变量：
    PERPLEXITY_API_KEY=pplx-...
    LANGSMITH_API_KEY=ls__...        # 可选，启用 LangSmith tracing
    LANGCHAIN_TRACING_V2=true        # 可选
"""

# import os
# from perplexity_client import PerplexityClient, SearchMode

# client = PerplexityClient(model="sonar-pro")


# # ─────────────────────────────────────────────────────────────────────────────
# # 示例 1：直接 chat_search（最简单，有 LangSmith trace）
# # ─────────────────────────────────────────────────────────────────────────────

# def example_chat_search():
#     result = client.chat_search(
#         "NVDA Q1 2025 earnings highlights",
#         mode=SearchMode.EXPLORATORY,
#     )
#     print("Answer:", result["answer"][:300])
#     print("Citations:", result["citations"][:3])


# # ─────────────────────────────────────────────────────────────────────────────
# # 示例 2：LangGraph ReAct agent，Perplexity 作为 search tool
# # ─────────────────────────────────────────────────────────────────────────────

# def example_langgraph_agent():
#     from langchain.chat_models import init_chat_model
#     from langgraph.prebuilt import create_react_agent

#     # 主模型可以用任何 LangChain 兼容的 LLM（这里用 GPT-4o）
#     # 如果想全用 Perplexity，把下面换成 client.get_llm()
#     llm = init_chat_model("gpt-4o", model_provider="openai")

#     # Perplexity Search 作为 tool
#     search_tool = client.get_search_tool(k=5)

#     agent = create_react_agent(llm, tools=[search_tool])

#     for step in agent.stream(
#         {"messages": [("user", "What are the latest AI chip regulations in 2025?")]},
#         stream_mode="values",
#     ):
#         step["messages"][-1].pretty_print()


# # ─────────────────────────────────────────────────────────────────────────────
# # 示例 3：ChatPerplexity 本身作为 agent 的 LLM（Sonar 内置 web search）
# # ─────────────────────────────────────────────────────────────────────────────

# def example_perplexity_as_llm():
#     from langgraph.prebuilt import create_react_agent

#     # ChatPerplexity 内置 web search，无需额外 tool
#     llm = client.get_llm()

#     # 还可以额外挂自定义 tools（如数据库查询、计算器等）
#     agent = create_react_agent(llm, tools=[])

#     result = agent.invoke({
#         "messages": [("user", "TSMC 2025 revenue forecast and margin outlook")]
#     })
#     print(result["messages"][-1].content)


# # ─────────────────────────────────────────────────────────────────────────────
# # 示例 4：Perplexity Agent API（/v1/responses，第三方模型 + 自动 web search）
# # ─────────────────────────────────────────────────────────────────────────────

# def example_agent_api():
#     # 使用 openai/gpt-4o 通过 Perplexity Agent API（自动 web search + 引用）
#     result = client.agent(
#         "What is the current federal funds rate and recent Fed statements?",
#         model="openai/gpt-4o",
#     )
#     print("Answer:", result["answer"][:400])
#     print("Citations:", result["citations"][:3])


# def example_agent_api_preset():
#     # 使用 Perplexity 预设（pro-search）
#     result = client.agent(
#         "Compare AMD vs NVIDIA GPU market share in data centers 2025",
#         preset="pro-search",
#     )
#     print(result["answer"][:400])


# def example_agent_api_stream():
#     # 流式输出
#     client.agent(
#         "Summarize today's top macro economic news",
#         model="openai/gpt-4o-mini",
#         stream=True,
#     )


# # ─────────────────────────────────────────────────────────────────────────────
# # 示例 5：LangChain RAG chain（Perplexity 作为 retriever）
# # ─────────────────────────────────────────────────────────────────────────────

# def example_rag_chain():
#     from langchain_perplexity import PerplexitySearchRetriever
#     from langchain_core.prompts import ChatPromptTemplate
#     from langchain_core.runnables import RunnablePassthrough
#     from langchain_core.output_parsers import StrOutputParser

#     llm = client.get_llm()
#     retriever = PerplexitySearchRetriever(
#         pplx_api_key=client.api_key,
#         k=3,
#     )

#     prompt = ChatPromptTemplate.from_template(
#         "Answer based on the following context:\n{context}\n\nQuestion: {question}"
#     )

#     def format_docs(docs):
#         return "\n\n".join(doc.page_content for doc in docs)

#     rag_chain = (
#         {"context": retriever | format_docs, "question": RunnablePassthrough()}
#         | prompt
#         | llm
#         | StrOutputParser()
#     )

#     answer = rag_chain.invoke("What is ITER's current construction status?")
#     print(answer)


# if __name__ == "__main__":
#     print("=== chat_search ===")
#     example_chat_search()

#     print("\n=== Agent API (openai/gpt-4o) ===")
#     example_agent_api()