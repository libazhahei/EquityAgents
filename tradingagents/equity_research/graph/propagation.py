"""Initial state factory for equity research graph."""

from __future__ import annotations

import uuid
from typing import Any

from tradingagents.equity_research.state.equity_research_state import empty_equity_research_state


class EquityPropagator:
    def __init__(self, max_recur_limit: int = 200):
        self.max_recur_limit = max_recur_limit

    def create_initial_state(self, ticker: str, **kwargs: Any) -> dict[str, Any]:
        state = empty_equity_research_state()
        state["ticker"] = ticker.upper()
        if "run_id" not in kwargs or not kwargs.get("run_id"):
            kwargs["run_id"] = str(uuid.uuid4())
        kwargs.setdefault("selected_section_ids", [])
        kwargs.setdefault("human_review_1_patch", {})
        kwargs.setdefault("human_review_2_patch", {})
        state.update(kwargs)
        return state

    def get_graph_args(
        self,
        callbacks: list | None = None,
        *,
        thread_id: str | None = None,
    ) -> dict[str, Any]:
        configurable: dict[str, Any] = {}
        if thread_id:
            configurable["thread_id"] = thread_id
        config: dict[str, Any] = {
            "recursion_limit": self.max_recur_limit,
            "configurable": configurable,
        }
        if callbacks:
            config["callbacks"] = callbacks
        return {"config": config}
