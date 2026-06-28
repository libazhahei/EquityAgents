"""Equity research tool errors."""

from __future__ import annotations


class ToolNotImplementedError(NotImplementedError):
    """Raised when a catalogued tool has no implementation yet."""

    def __init__(self, tool_name: str, detail: str | None = None) -> None:
        self.tool_name = tool_name
        self.detail = detail
        message = f"Tool '{tool_name}' is not implemented yet."
        if detail:
            message = f"{message} {detail}"
        super().__init__(message)


def raise_not_implemented(tool_name: str, detail: str | None = None) -> None:
    raise ToolNotImplementedError(tool_name, detail)
