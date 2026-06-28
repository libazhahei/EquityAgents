"""Adapters between LangChain @tool objects and registry callables."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.tools import BaseTool


def make_registry_callable(tool: BaseTool) -> Callable[..., Any]:
    """Expose a LangChain tool as a plain callable for skill handlers."""

    def _call(*args: Any, **kwargs: Any) -> Any:
        payload = _bind_tool_input(tool, args, kwargs)
        result = tool.invoke(payload)
        return _normalize_tool_result(result)

    _call.__name__ = getattr(tool, "name", "tool")
    return _call


def get_base_tool(tool: BaseTool | Callable[..., Any]) -> BaseTool:
    if isinstance(tool, BaseTool):
        return tool
    raise TypeError(f"Expected LangChain BaseTool, got {type(tool)!r}")


def _bind_tool_input(tool: BaseTool, args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    if kwargs:
        return kwargs
    if not args:
        return {}
    schema = tool.args_schema
    if schema is None:
        raise TypeError(f"Tool {tool.name!r} received positional args but has no schema")
    fields = list(schema.model_fields.keys())
    if len(args) == len(fields):
        return dict(zip(fields, args, strict=True))
    if len(args) == 1 and len(fields) == 1:
        return {fields[0]: args[0]}
    if len(args) == 2 and len(fields) >= 2 and fields[0] == "state":
        return {fields[0]: args[0], fields[1]: args[1]}
    raise TypeError(
        f"Could not bind positional args for tool {tool.name!r}: "
        f"args={args!r}, fields={fields!r}"
    )


def _normalize_tool_result(result: Any) -> Any:
    if isinstance(result, str):
        stripped = result.strip()
        if stripped.startswith("{") or stripped.startswith("["):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return result
    return result
