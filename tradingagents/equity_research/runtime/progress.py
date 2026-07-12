"""Thin progress event bus for equity research runtime (SSE-ready)."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol


ProgressStatus = str  # started|succeeded|failed|interrupted|waiting_human|resumed


@dataclass
class ProgressEvent:
    """Versioned progress event for CLI / future SSE sinks."""

    version: int = 1
    stage: str = ""
    node: str = ""
    status: ProgressStatus = "started"
    run_id: str = ""
    thread_id: str = ""
    ticker: str = ""
    section_id: str | None = None
    checkpoint_ns: str | None = None
    ts: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProgressSink(Protocol):
    def __call__(self, event: ProgressEvent) -> None: ...


class ProgressBus:
    """In-process fan-out bus with pluggable sinks."""

    def __init__(self, *, history_size: int = 512) -> None:
        self._sinks: list[ProgressSink] = []
        self._history: deque[ProgressEvent] = deque(maxlen=history_size)

    def subscribe(self, sink: ProgressSink) -> Callable[[], None]:
        self._sinks.append(sink)

        def unsubscribe() -> None:
            try:
                self._sinks.remove(sink)
            except ValueError:
                pass

        return unsubscribe

    def emit(self, **kwargs: Any) -> ProgressEvent:
        if not kwargs.get("ts"):
            kwargs["ts"] = datetime.now(timezone.utc).isoformat()
        event = ProgressEvent(**kwargs)
        self._history.append(event)
        for sink in list(self._sinks):
            sink(event)
        return event

    def iter_events(self) -> Iterator[ProgressEvent]:
        yield from list(self._history)

    def clear_history(self) -> None:
        self._history.clear()


def stdout_progress_sink(event: ProgressEvent) -> None:
    section = f" section={event.section_id}" if event.section_id else ""
    print(f"[{event.status}] {event.stage}/{event.node}{section}")
