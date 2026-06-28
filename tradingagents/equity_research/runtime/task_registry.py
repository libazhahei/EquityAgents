"""Registry of available TaskProfile instances."""

from __future__ import annotations

from tradingagents.equity_research.runtime.task_profile import TaskProfile


class TaskRegistry:
    def __init__(self) -> None:
        self._profiles: dict[str, TaskProfile] = {}

    def register(self, profile: TaskProfile) -> None:
        self._profiles[profile.task_id] = profile

    def get(self, task_id: str) -> TaskProfile:
        if task_id not in self._profiles:
            raise KeyError(f"Unknown task_id: {task_id}")
        return self._profiles[task_id]

    def list_ids(self) -> list[str]:
        return sorted(self._profiles.keys())

    def format_catalog(self) -> str:
        lines = ["| task_id | objective | dimensions |", "|---|---|---|"]
        for task_id in self.list_ids():
            profile = self._profiles[task_id]
            dims = ", ".join(profile.dimensions[:3])
            if len(profile.dimensions) > 3:
                dims += ", ..."
            lines.append(f"| {task_id} | {profile.objective[:60]} | {dims} |")
        return "\n".join(lines)
