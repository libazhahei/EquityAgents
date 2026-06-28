"""LangChain artifact writer tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import artifact_tools


@tool
def markdown_writer(
    content: Annotated[str, "Markdown content"],
    path: Annotated[str, "Output path relative to workspace root"],
) -> dict[str, Any]:
    """Write a markdown file to the workspace."""
    return artifact_tools.markdown_writer(content, path)


@tool
def json_writer(
    data: Annotated[dict | list, "JSON-serializable data"],
    path: Annotated[str, "Output path relative to workspace root"],
) -> dict[str, Any]:
    """Write a JSON file to the workspace."""
    return artifact_tools.json_writer(data, path)
