"""Parameterized skill selector nodes for research subgraphs (agent + ToolNode)."""

from __future__ import annotations

import json
from typing import Any, Callable

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.prebuilt import ToolNode

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.skills.catalog import format_catalog_for_prompt
from tradingagents.equity_research.skills.loader import format_skill_prompt
from tradingagents.equity_research.skills.registry import SkillRegistry
from tradingagents.equity_research.tools.skill_tools import (
    make_load_research_skills_tool,
    parse_load_skills_result,
)


def build_skill_context(registry: SkillRegistry, skill_names: list[str], state: dict[str, Any]) -> dict[str, Any]:
    loaded = [registry.read_skill(name) for name in skill_names]
    prompt_parts = [format_skill_prompt(item.prompt_template, state) for item in loaded]
    guidance_parts = [item.query_guidance for item in loaded if item.query_guidance]
    constraints_parts = [item.constraints for item in loaded if item.constraints]
    tools: list[str] = []
    for item in loaded:
        tools.extend(item.tools)
    return {
        "names": skill_names,
        "descriptions": [item.manifest.description for item in loaded],
        "when_to_use": [item.manifest.when_to_use for item in loaded],
        "constraints": "\n\n".join(constraints_parts),
        "prompt_template": "\n\n".join(prompt_parts),
        "query_guidance": "\n\n".join(guidance_parts),
        "tools": list(dict.fromkeys(tools)),
        "compatible_with": list({c for item in loaded for c in item.compatible_with}),
    }


def _skill_selection_prompt(
    state: dict[str, Any],
    catalog_table: str,
    ticker: str,
    *,
    max_skills: int,
    prompt_builder: Callable[[dict[str, Any], str, str], str] | None = None,
) -> str:
    if prompt_builder:
        return prompt_builder(state, catalog_table, ticker)
    return (
        f"Select equity research skills to load for {ticker}.\n"
        f"Sector: {state.get('sector', '')}\n"
        f"Report type: {state.get('report_type', '')}\n"
        f"Instrument context: {state.get('instrument_context', '')[:500]}\n\n"
        f"Skill catalog (read descriptions and when_to_use before deciding):\n{catalog_table}\n\n"
        "Call load_research_skills with skill names from the catalog only.\n"
        "You may pass an empty list if no skill is needed.\n"
        f"Return at most {max_skills} skill names."
    )


def create_skill_selector_agent(
    deps: EquityResearchDeps,
    *,
    graph_name: str,
    objective: str,
    max_skills: int = 2,
    registry: SkillRegistry | None = None,
    prompt_builder: Callable[[dict[str, Any], str, str], str] | None = None,
):
    skill_reg = registry or SkillRegistry(deps=deps)
    load_tool = make_load_research_skills_tool(
        skill_reg,
        graph_name=graph_name,
        objective=objective,
        max_skills=max_skills,
    )

    def skill_selector_agent(state: dict[str, Any]) -> dict[str, Any]:
        ticker = state.get("ticker", "")
        eligible = skill_reg.get_eligible_catalog(graph_name)
        catalog_table = format_catalog_for_prompt(eligible)
        prompt = _skill_selection_prompt(
            state,
            catalog_table,
            ticker,
            max_skills=max_skills,
            prompt_builder=prompt_builder,
        )
        messages = list(state.get("messages", []))
        if not messages:
            messages = [HumanMessage(content=prompt)]
        chain = deps.quick_llm.bind_tools([load_tool])
        result = chain.invoke(messages)
        return {"messages": messages + [result]}

    return skill_selector_agent


def create_skill_tools_node(
    deps: EquityResearchDeps,
    *,
    graph_name: str,
    objective: str,
    max_skills: int = 2,
    registry: SkillRegistry | None = None,
):
    skill_reg = registry or SkillRegistry(deps=deps)
    load_tool = make_load_research_skills_tool(
        skill_reg,
        graph_name=graph_name,
        objective=objective,
        max_skills=max_skills,
    )
    return ToolNode([load_tool])


def create_skill_context_apply(
    deps: EquityResearchDeps,
    *,
    graph_name: str,
    objective: str,
    max_skills: int = 2,
    registry: SkillRegistry | None = None,
    trace_name: str | None = None,
):
    skill_reg = registry or SkillRegistry(deps=deps)
    agent_trace = trace_name or f"{graph_name}_skill_selector"
    fallback_name = skill_reg.select_for_objective(objective)

    def skill_context_apply(state: dict[str, Any]) -> dict[str, Any]:
        errors = list(state.get("errors", []))
        messages = list(state.get("messages", []))
        skill_names: list[str] = []
        catalog_snapshot = [e.to_prompt_dict() for e in skill_reg.get_eligible_catalog(graph_name)]

        try:
            for message in reversed(messages):
                if isinstance(message, ToolMessage):
                    payload = parse_load_skills_result(str(message.content))
                    skill_names = list(payload.get("skill_names") or [])
                    catalog_snapshot = list(payload.get("catalog_snapshot") or catalog_snapshot)
                    break
                if isinstance(message, AIMessage) and not message.tool_calls:
                    break

            if not skill_names:
                skill_names = [fallback_name]

            for name in skill_names:
                skill_reg.read_skill(name)
            context = build_skill_context(skill_reg, skill_names, state)
            updates: dict[str, Any] = {
                "active_skills": skill_names,
                "active_skill_context": context,
                "skill_catalog": catalog_snapshot,
                "loaded_skills": list(skill_names),
                "messages": [],
            }
            updates.update(deps.trace({**state, **updates}, agent_trace, {
                "skills": skill_names,
                "catalog_size": len(catalog_snapshot),
            }))
            return updates
        except Exception as exc:
            errors.append(f"skill_context_apply: {exc}")
            skill_reg.read_skill(fallback_name)
            context = build_skill_context(skill_reg, [fallback_name], state)
            return {
                "errors": errors,
                "active_skills": [fallback_name],
                "active_skill_context": context,
                "skill_catalog": catalog_snapshot,
                "loaded_skills": [fallback_name],
                "messages": [],
            }

    return skill_context_apply


def create_skill_selector(
    deps: EquityResearchDeps,
    *,
    graph_name: str,
    objective: str,
    max_skills: int = 2,
    registry: SkillRegistry | None = None,
    trace_name: str | None = None,
    prompt_builder: Callable[[dict[str, Any], str, str], str] | None = None,
):
    """Backward-compatible single-node wrapper (agent → tools → apply)."""
    agent = create_skill_selector_agent(
        deps,
        graph_name=graph_name,
        objective=objective,
        max_skills=max_skills,
        registry=registry,
        prompt_builder=prompt_builder,
    )
    tools = create_skill_tools_node(
        deps,
        graph_name=graph_name,
        objective=objective,
        max_skills=max_skills,
        registry=registry,
    )
    apply = create_skill_context_apply(
        deps,
        graph_name=graph_name,
        objective=objective,
        max_skills=max_skills,
        registry=registry,
        trace_name=trace_name,
    )

    def skill_selector(state: dict[str, Any]) -> dict[str, Any]:
        working = dict(state)
        try:
            working = {**working, **agent(state)}
            last = working["messages"][-1]
            if isinstance(last, AIMessage) and last.tool_calls:
                working = {**working, **tools(working)}
        except Exception:
            pass
        return apply(working)

    return skill_selector


# Backward-compatible alias for internal imports
_build_skill_context = build_skill_context
