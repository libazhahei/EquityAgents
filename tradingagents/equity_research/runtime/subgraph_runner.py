"""Generic runner for TaskProfile-driven research subgraphs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from tradingagents.equity_research.agents.deps import EquityResearchDeps
from tradingagents.equity_research.runtime.state import AgentState
from tradingagents.equity_research.runtime.subgraph import GenericResearchSubgraph
from tradingagents.equity_research.runtime.task_profile import TaskProfile


def create_run_profile_subgraph(
    deps: EquityResearchDeps,
    profile: TaskProfile,
    *,
    seed_state: Callable[[dict[str, Any], TaskProfile], AgentState],
    map_result: Callable[[dict[str, Any], dict[str, Any], TaskProfile], dict[str, Any]],
    human_review_config: dict[str, Any] | None = None,
    checkpointer=None,
):
    compiled = GenericResearchSubgraph(deps, profile).compile(
        checkpointer=checkpointer,
        human_review_config=human_review_config,
    )

    def run_subgraph(state: dict[str, Any]) -> dict[str, Any]:
        subgraph_input = seed_state(state, profile)
        result = compiled.invoke(subgraph_input)
        return map_result(state, result, profile)

    return run_subgraph
