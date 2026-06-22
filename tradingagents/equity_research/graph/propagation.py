"""Initial state factory for equity research graph."""

from __future__ import annotations

from typing import Any

from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


class EquityPropagator:
    def __init__(self, max_recur_limit: int = 200):
        self.max_recur_limit = max_recur_limit

    def create_initial_state(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        state = empty_equity_research_state()
        state["ticker"] = ticker.upper()
        state.update(kwargs)
        return state

    def get_graph_args(self, callbacks: list | None = None) -> dict[str, Any]:
        config: dict[str, Any] = {"recursion_limit": self.max_recur_limit}
        if callbacks:
            config["callbacks"] = callbacks
        return {"config": config}
