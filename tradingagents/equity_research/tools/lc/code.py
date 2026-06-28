"""LangChain code and sandbox tools."""

from __future__ import annotations

from typing import Annotated, Any

from langchain_core.tools import tool

from tradingagents.equity_research.tools import code_tools


@tool
def code_reader(path: Annotated[str, "Code file path relative to code root"]) -> dict[str, Any]:
    """Read a code file from the workspace."""
    return code_tools.code_reader(path)


@tool
def code_search(
    query: Annotated[str, "Text to search for in code"],
    path: Annotated[str, "Directory or file path to search"] = ".",
) -> dict[str, Any]:
    """Search project code for a query string."""
    return code_tools.code_search(query, path)


@tool
def code_writer(
    path: Annotated[str, "Code file path relative to code root"],
    content: Annotated[str, "Full file content to write"],
) -> dict[str, Any]:
    """Write or overwrite a code file (disabled unless enabled in config)."""
    return code_tools.code_writer(path, content)


@tool
def python_exec_sandbox(code: Annotated[str, "Python code to execute in E2B sandbox"]) -> dict[str, Any]:
    """Execute Python code in an isolated E2B sandbox."""
    return code_tools.python_exec_sandbox(code)


@tool
def shell_exec_sandbox(command: Annotated[str, "Shell command to execute in E2B sandbox"]) -> dict[str, Any]:
    """Execute an allowlisted shell command in E2B sandbox."""
    return code_tools.shell_exec_sandbox(command)
