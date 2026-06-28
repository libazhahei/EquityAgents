"""Runnable skill wrapper and prompt-based execution."""

from __future__ import annotations

import importlib
import json
from typing import Any

from tradingagents.equity_research.skills.base import (
    LoadedSkill,
    SkillHandler,
    SkillInput,
    SkillManifest,
    SkillOutput,
)
from tradingagents.equity_research.skills.loader import format_skill_prompt


class PromptSkillRunner:
    """Execute a skill via LLM prompt + optional tool calls (single round)."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def run(self, loaded: LoadedSkill, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        state = input.state_snapshot
        prompt_body = format_skill_prompt(loaded.prompt_template, state)
        constraints = loaded.constraints
        tool_summaries = []
        for name, fn in tools.items():
            try:
                if name == "get_consensus_estimates":
                    tool_summaries.append(json.dumps(fn(state.get("ticker", "")), default=str)[:500])
                elif name == "get_financial_statements":
                    tool_summaries.append(json.dumps(fn(state.get("ticker", "")), default=str)[:500])
                elif name == "get_news":
                    tool_summaries.append(str(fn(state.get("ticker", "")))[:500])
                elif name == "retrieve_claims_by_section":
                    tool_summaries.append(json.dumps(fn(state, ""), default=str)[:500])
            except Exception:
                continue

        if self.llm is None:
            return SkillOutput(
                summary=f"{loaded.manifest.name}: {prompt_body[:300]}",
                confidence=0.4,
                artifacts={"tool_summaries": tool_summaries},
            )

        prompt = (
            f"Skill: {loaded.manifest.name}\n"
            f"Objective: {input.objective}\n"
            f"Constraints:\n{constraints}\n\n"
            f"Instructions:\n{prompt_body}\n\n"
            f"Tool outputs:\n{json.dumps(tool_summaries, default=str)[:2000]}\n\n"
            "Return a concise summary of findings."
        )
        response = self.llm.invoke(prompt)
        text = response.content if hasattr(response, "content") else str(response)
        return SkillOutput(summary=text[:2000], confidence=0.55, artifacts={"tool_summaries": tool_summaries})


def resolve_handler(handler_path: str) -> SkillHandler:
    module_path, _, attr = handler_path.partition(":")
    if not module_path or not attr:
        raise ValueError(f"Invalid handler path: {handler_path}")
    module = importlib.import_module(module_path)
    target = getattr(module, attr)
    if isinstance(target, type):
        return target()
    if callable(target):
        instance = target()
        if hasattr(instance, "run"):
            return instance
        raise ValueError(f"Handler callable did not return runnable instance: {handler_path}")
    raise ValueError(f"Handler not found: {handler_path}")


class RunnableSkill:
    def __init__(
        self,
        loaded: LoadedSkill,
        *,
        llm: Any | None = None,
        handler: SkillHandler | None = None,
    ) -> None:
        self.loaded = loaded
        self.name = loaded.name
        self._manifest = SkillManifest.from_loaded(loaded)
        self._handler = handler
        self._prompt_runner = PromptSkillRunner(llm)

    @property
    def manifest(self) -> SkillManifest:
        return self._manifest

    def run(self, input: SkillInput, tools: dict[str, Any]) -> SkillOutput:
        if self._handler is not None:
            return self._handler.run(self.loaded, input, tools)
        return self._prompt_runner.run(self.loaded, input, tools)

    @classmethod
    def from_loaded(cls, loaded: LoadedSkill, *, llm: Any | None = None) -> RunnableSkill:
        handler: SkillHandler | None = None
        if loaded.handler:
            handler = resolve_handler(loaded.handler)
        return cls(loaded, llm=llm, handler=handler)
