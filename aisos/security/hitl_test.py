"""Tests for HITL gate."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from aisos.orchestration.event_bus import Event, EventBus
from aisos.security.hitl import HITLDenied, HITLGate, REQUEST_TOPIC, RESPONSE_TOPIC
from aisos.tools.base import BaseTool


class _In(BaseModel):
    pass


class _LowTool(BaseTool):
    name = "low"
    description = "low"
    input_schema = _In
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: _In) -> dict:  # type: ignore[override]
        return {}


class _HighTool(BaseTool):
    name = "high"
    description = "high"
    input_schema = _In
    risk_level = "high"
    required_scope = "write"

    async def run(self, input: _In) -> dict:  # type: ignore[override]
        return {}


@pytest.mark.asyncio
async def test_low_risk_skips_gate() -> None:
    bus = EventBus()
    gate = HITLGate(bus, timeout_s=0.1)
    await gate.gate(_LowTool(), {})  # would deadlock if it waited


@pytest.mark.asyncio
async def test_high_risk_approve_unblocks() -> None:
    bus = EventBus()
    gate = HITLGate(bus, timeout_s=2.0)
    requests = bus.subscribe(REQUEST_TOPIC)

    async def operator() -> None:
        async for ev in requests:
            await bus.publish(
                Event(RESPONSE_TOPIC, {"request_id": ev.payload["request_id"], "approved": True})
            )
            return

    op_task = asyncio.create_task(operator())
    await gate.gate(_HighTool(), {"x": 1})
    await op_task


@pytest.mark.asyncio
async def test_high_risk_deny_raises() -> None:
    bus = EventBus()
    gate = HITLGate(bus, timeout_s=2.0)
    requests = bus.subscribe(REQUEST_TOPIC)

    async def operator() -> None:
        async for ev in requests:
            await bus.publish(
                Event(
                    RESPONSE_TOPIC,
                    {"request_id": ev.payload["request_id"], "approved": False, "reason": "no"},
                )
            )
            return

    op_task = asyncio.create_task(operator())
    with pytest.raises(HITLDenied):
        await gate.gate(_HighTool(), {})
    await op_task


@pytest.mark.asyncio
async def test_high_risk_timeout_raises() -> None:
    bus = EventBus()
    gate = HITLGate(bus, timeout_s=0.1)
    with pytest.raises(HITLDenied):
        await gate.gate(_HighTool(), {})
