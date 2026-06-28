"""Tool registry for equity research skills."""

from __future__ import annotations

from typing import Any, Callable

from langchain_core.tools import BaseTool

from tradingagents.equity_research.tools.lc import STATIC_LANGCHAIN_TOOLS, build_system_langchain_tools
from tradingagents.equity_research.tools.perplexity_tool import make_perplexity_search_tool
from tradingagents.equity_research.tools.tool_adapters import make_registry_callable


class ToolRegistry:
    """Registry of equity research tools backed by LangChain @tool definitions."""

    def __init__(self, deps: Any | None = None, skill_registry: Any | None = None):
        self.deps = deps
        self._skill_registry = skill_registry
        self._langchain_tools: dict[str, BaseTool] = dict(STATIC_LANGCHAIN_TOOLS)
        self._tools: dict[str, Callable[..., Any]] = {}
        self._register_static_tools()
        self._bind_system_tools()
        if deps is not None:
            self._register_langchain_tool("perplexity_search", make_perplexity_search_tool(deps))

    def set_skill_registry(self, skill_registry: Any) -> None:
        self._skill_registry = skill_registry
        self._bind_system_tools()

    def _registered_set(self) -> set[str]:
        return set(self._tools.keys())

    def _register_langchain_tool(self, name: str, lc_tool: BaseTool) -> None:
        self._langchain_tools[name] = lc_tool
        self._tools[name] = make_registry_callable(lc_tool)

    def _register_static_tools(self) -> None:
        for name, lc_tool in STATIC_LANGCHAIN_TOOLS.items():
            self._register_langchain_tool(name, lc_tool)

    def _bind_system_tools(self) -> None:
        system_lc = build_system_langchain_tools(
            registered=self._registered_set,
            skill_registry=self._skill_registry,
            deps=self.deps,
        )
        for name, lc_tool in system_lc.items():
            self._register_langchain_tool(name, lc_tool)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> Callable[..., Any]:
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not registered")
        return self._tools[name]

    def get_langchain_tool(self, name: str) -> BaseTool:
        if name not in self._langchain_tools:
            raise KeyError(f"LangChain tool '{name}' not registered")
        return self._langchain_tools[name]

    def list_langchain_tools(self) -> list[BaseTool]:
        return list(self._langchain_tools.values())

    def for_skill(self, allowed_tools: list[str]) -> dict[str, Callable[..., Any]]:
        return {name: self._tools[name] for name in allowed_tools if name in self._tools}

    def for_skill_langchain(self, allowed_tools: list[str]) -> list[BaseTool]:
        return [self._langchain_tools[name] for name in allowed_tools if name in self._langchain_tools]

    def call(self, name: str, *args, **kwargs) -> Any:
        return self.get(name)(*args, **kwargs)
