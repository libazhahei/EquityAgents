"""E2B sandbox for code execution tools."""

from __future__ import annotations

import os
import re
from typing import Any

from tradingagents.dataflows.errors import VendorNotConfiguredError

_SHELL_DENY = re.compile(
    r"\b(rm\s+-rf|curl\b|wget\b|chmod\b|chown\b|sudo\b|mkfs\b|dd\b|>\s*/dev/)\b",
    re.IGNORECASE,
)
_SHELL_ALLOW_PREFIXES = ("python", "pip", "ls", "pwd", "cat", "echo", "pytest", "uv ")


class E2BSandbox:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("E2B_API_KEY", "")

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def _ensure_configured(self) -> None:
        if not self.api_key:
            raise VendorNotConfiguredError("E2B_API_KEY is not set")

    def run_python(self, code: str, timeout: int = 60) -> dict[str, Any]:
        self._ensure_configured()
        try:
            from e2b_code_interpreter import Sandbox
        except ImportError as exc:
            raise VendorNotConfiguredError("e2b package not installed") from exc

        with Sandbox(api_key=self.api_key) as sandbox:
            execution = sandbox.run_code(code, timeout=timeout)
            return {
                "stdout": "\n".join(execution.logs.stdout) if execution.logs else "",
                "stderr": "\n".join(execution.logs.stderr) if execution.logs else "",
                "error": str(execution.error) if execution.error else None,
                "results": [str(r) for r in (execution.results or [])],
            }

    def run_shell(self, command: str, timeout: int = 30) -> dict[str, Any]:
        self._ensure_configured()
        if _SHELL_DENY.search(command):
            return {"stdout": "", "stderr": "Command blocked by security policy", "exit_code": 1}
        if not any(command.strip().startswith(p) for p in _SHELL_ALLOW_PREFIXES):
            return {
                "stdout": "",
                "stderr": f"Command not in allowlist: {command}",
                "exit_code": 1,
            }

        try:
            from e2b import Sandbox
        except ImportError as exc:
            raise VendorNotConfiguredError("e2b package not installed") from exc

        with Sandbox(api_key=self.api_key) as sandbox:
            result = sandbox.commands.run(command, timeout=timeout)
            return {
                "stdout": result.stdout or "",
                "stderr": result.stderr or "",
                "exit_code": result.exit_code,
            }
