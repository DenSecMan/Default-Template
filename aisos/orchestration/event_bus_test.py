"""Tests for orchestration.event_bus."""

from __future__ import annotations

import asyncio

import pytest

from aisos.orchestration.event_bus import Event, EventBus


@pytest.mark.asyncio
async def test_publish_delivers_in_order() -> None:
    bus = EventBus()
    sub = bus.subscribe("trace.node")
    received: list[Event] = []

    async def consume() -> None:
        async for ev in sub:
            received.append(ev)
            if len(received) == 3:
                break

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0)  # let subscribe register
    for i in range(3):
        await bus.publish(Event("trace.node", {"i": i}))
    await consumer
    assert [ev.payload["i"] for ev in received] == [0, 1, 2]


@pytest.mark.asyncio
async def test_no_delivery_to_other_topics() -> None:
    bus = EventBus()
    sub_a = bus.subscribe("a")
    received: list[Event] = []

    async def consume() -> None:
        async for ev in sub_a:
            received.append(ev)
            break

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    await bus.publish(Event("b", {}))
    await bus.publish(Event("a", {"x": 1}))
    await task
    assert received[0].payload == {"x": 1}
