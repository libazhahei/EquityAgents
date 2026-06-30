"""Dynamic research planning — section question tree compiler."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.agents.section_planner.aggregate import (
    aggregate_research_plan,
    derive_strategy_shim,
    merge_exploration_graph,
    planner_section_ids,
)
from tradingagents.equity_research.agents.section_planner.state import (
    build_section_planner_request,
    empty_section_planner_state,
)
from tradingagents.equity_research.agents.section_planner.subgraph import SectionPlannerSubgraph
from tradingagents.equity_research.runtime.exploration_graph import ExplorationGraph


def create_dynamic_planning(deps: EquityResearchDeps):
    compiled = SectionPlannerSubgraph(deps).compile()

    def dynamic_planning(state: dict[str, Any]) -> dict[str, Any]:
        background = {
            "consensus_report": state.get("consensus_report", ""),
            "assumption_report": state.get("assumption_report", ""),
            "final_report": state.get("final_report") or "",
        }
        enable_grounding = bool(
            state.get("enable_planner_grounding")
            or deps.config.get("equity_research", {}).get("planner_grounding", False)
        )

        section_plans = dict(state.get("section_plans", {}))
        exploration = ExplorationGraph.from_dict(state.get("planner_exploration_graph"))
        api_calls = int(state.get("api_calls", 0))
        research_traces = list(state.get("research_traces", []))
        errors = list(state.get("errors", []))

        for section_id in planner_section_ids():
            req = build_section_planner_request(
                state,
                section_id,
                background,
                enable_grounding=enable_grounding,
            )
            subgraph_input = empty_section_planner_state(req)
            subgraph_input["api_calls"] = api_calls
            subgraph_input["research_traces"] = research_traces
            subgraph_input["errors"] = errors

            try:
                result = compiled.invoke(subgraph_input)
                section_plans[section_id] = result.get("plan", {})
                merge_exploration_graph(exploration, result)
                api_calls = int(result.get("api_calls", api_calls))
                research_traces = list(result.get("research_traces", research_traces))
                errors = list(result.get("errors", errors))
            except Exception as exc:
                errors.append(f"section_planner[{section_id}]: {exc}")

        strategy = derive_strategy_shim(state, section_plans)
        updates: dict[str, Any] = {
            "section_plans": section_plans,
            "research_plan": aggregate_research_plan(section_plans),
            "research_strategy": strategy,
            "planner_exploration_graph": exploration.to_dict(),
            "research_phase": strategy.get("stage", state.get("research_phase", "orientation")),
            "api_calls": api_calls,
            "research_traces": research_traces,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        if errors:
            updates["errors"] = errors
        updates.update(deps.trace({**state, **updates}, "dynamic_planning", {
            "sections_planned": len(section_plans),
            "stage": strategy.get("stage"),
            "grounding": enable_grounding,
        }))
        return updates

    return dynamic_planning
