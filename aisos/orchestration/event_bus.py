"""In-process asyncio pub/sub."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator


@dataclass
class Event:
    topic: str
    payload: dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Topic -> list of asyncio.Queue subscribers. FIFO per subscriber."""

    def __init__(self) -> None:
        self._subs: dict[str, list[asyncio.Queue[Event]]] = {}

    async def publish(self, event: Event) -> None:
        for q in list(self._subs.get(event.topic, [])):
            await q.put(event)

    def subscribe(self, topic: str, maxsize: int = 0) -> AsyncIterator[Event]:
        queue: asyncio.Queue[Event] = asyncio.Queue(maxsize=maxsize)
        self._subs.setdefault(topic, []).append(queue)

        async def _iter() -> AsyncIterator[Event]:
            try:
                while True:
                    yield await queue.get()
            finally:
                self._subs.get(topic, []).remove(queue)

        return _iter()

    def topics(self) -> list[str]:
        return list(self._subs)


__all__ = ["Event", "EventBus"]
