"""Human-in-the-loop gate. High-risk tools must wait for an approval event."""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import Any

from aisos.orchestration.event_bus import Event, EventBus
from aisos.tools.base import BaseTool

REQUEST_TOPIC = "hitl.request"
RESPONSE_TOPIC = "hitl.response"


class HITLDenied(RuntimeError):
    """Operator denied a high-risk tool call."""


@dataclass
class HITLRequest:
    request_id: str
    tool_name: str
    risk_level: str
    summary: dict[str, Any]


class HITLGate:
    """Publishes hitl.request, awaits matching hitl.response."""

    def __init__(self, bus: EventBus, timeout_s: float | None = None) -> None:
        self._bus = bus
        self._timeout = timeout_s

    async def gate(self, tool: BaseTool, args: dict[str, Any]) -> None:
        if tool.risk_level != "high":
            return
        request_id = uuid.uuid4().hex
        sub = self._bus.subscribe(RESPONSE_TOPIC)
        await self._bus.publish(
            Event(
                REQUEST_TOPIC,
                {
                    "request_id": request_id,
                    "tool_name": tool.name,
                    "risk_level": tool.risk_level,
                    "summary": dict(args),
                },
            )
        )

        async def _wait() -> Event:
            async for ev in sub:
                if ev.payload.get("request_id") == request_id:
                    return ev
            raise RuntimeError("HITL subscription closed")

        try:
            response = await asyncio.wait_for(_wait(), timeout=self._timeout)
        except asyncio.TimeoutError as e:
            raise HITLDenied(
                f"HITL approval for tool '{tool.name}' timed out"
            ) from e
        if not response.payload.get("approved"):
            reason = response.payload.get("reason", "denied")
            raise HITLDenied(f"HITL denied tool '{tool.name}': {reason}")


__all__ = ["HITLDenied", "HITLGate", "HITLRequest", "REQUEST_TOPIC", "RESPONSE_TOPIC"]
