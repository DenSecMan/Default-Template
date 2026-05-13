"""Tests for trace event emitter."""

from __future__ import annotations

import asyncio

import pytest

from aisos.observability.trace import TRACE_TOPIC, Tracer
from aisos.orchestration.event_bus import EventBus


@pytest.mark.asyncio
async def test_emits_lifecycle_events() -> None:
    bus = EventBus()
    sub = bus.subscribe(TRACE_TOPIC)
    received = []

    async def consume() -> None:
        async for ev in sub:
            received.append(ev)
            if len(received) == 2:
                break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    tracer = Tracer(bus)
    await tracer.emit("step1", "running", agent="planner")
    await tracer.emit("step1", "complete", agent="planner")
    await task
    assert [e.payload["status"] for e in received] == ["running", "complete"]
    assert received[0].payload["node_id"] == "step1"
