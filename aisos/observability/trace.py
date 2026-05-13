"""Execution trace emitter — publishes trace.node events for the TUI."""

from __future__ import annotations

import time
from typing import Any

from aisos.orchestration.event_bus import Event, EventBus
from aisos.orchestration.state import StepStatus

TRACE_TOPIC = "trace.node"


class Tracer:
    """Thin wrapper that publishes node lifecycle events."""

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def emit(
        self,
        node_id: str,
        status: StepStatus,
        agent: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        await self._bus.publish(
            Event(
                TRACE_TOPIC,
                {
                    "node_id": node_id,
                    "status": status,
                    "agent": agent,
                    "ts": time.time(),
                    "detail": detail or {},
                },
            )
        )


__all__ = ["TRACE_TOPIC", "Tracer"]
