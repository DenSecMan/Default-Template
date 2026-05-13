"""End-to-end orchestration tests using mock provider + real registries."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from aisos.config import load_config
from aisos.intelligence.base_test import MockProvider
from aisos.intelligence.router import Router
from aisos.observability.audit_log import AuditLog
from aisos.observability.cost_tracker import CostTracker
from aisos.orchestration.event_bus import Event, EventBus
from aisos.orchestration.orchestrator import Orchestrator
from aisos.orchestration.planner import Planner
from aisos.security.hitl import HITLDenied, REQUEST_TOPIC, RESPONSE_TOPIC
from aisos.tools.registry import ToolRegistry


def _make_cfg(tmp_path: Path) -> object:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        'max_steps = 25\n'
        '[routing]\n'
        'default = { provider = "mock", model = "m" }\n'
        'plan    = { provider = "mock", model = "m" }\n'
        '[rbac]\n'
        'planner = ["read", "write", "compute"]\n'
        'default = ["read"]\n'
        '[cost]\n',
        encoding="utf-8",
    )
    return load_config(env_file=env, toml_file=toml)


def _registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.discover("tools")
    return reg


@pytest.mark.asyncio
async def test_echo_tool_end_to_end(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    bus = EventBus()
    plan = json.dumps(
        {
            "plan": [
                {
                    "id": "s1",
                    "description": "echo greeting",
                    "tool": "echo",
                    "args": {"text": "hello e2e"},
                    "depends_on": [],
                }
            ]
        }
    )
    provider = MockProvider(chat_response=plan)
    router = Router(cfg, {"mock": provider})  # type: ignore[arg-type]
    planner = Planner(router)
    tools = _registry()
    audit = AuditLog(tmp_path / "audit.log")
    cost = CostTracker(cfg)  # type: ignore[arg-type]
    orch = Orchestrator(
        cfg, bus, planner, tools, agent_name="planner", audit=audit, cost_tracker=cost,
    )
    result = await orch.run("say hello")
    assert "hello e2e" in result.output_text
    assert result.state.plan[0].status == "complete"
    rows = audit.read_all()
    assert any(r["action"] == "echo" for r in rows)


@pytest.mark.asyncio
async def test_high_risk_tool_approved(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    bus = EventBus()
    plan = json.dumps(
        {
            "plan": [
                {
                    "id": "s1",
                    "description": "do dangerous thing",
                    "tool": "dangerous_demo",
                    "args": {"payload": "go"},
                    "depends_on": [],
                }
            ]
        }
    )
    provider = MockProvider(chat_response=plan)
    router = Router(cfg, {"mock": provider})  # type: ignore[arg-type]
    planner = Planner(router)
    tools = _registry()
    orch = Orchestrator(
        cfg, bus, planner, tools, agent_name="planner", hitl_timeout_s=2.0,
    )
    requests = bus.subscribe(REQUEST_TOPIC)

    async def operator() -> None:
        async for ev in requests:
            await bus.publish(
                Event(RESPONSE_TOPIC, {"request_id": ev.payload["request_id"], "approved": True})
            )
            return

    op = asyncio.create_task(operator())
    result = await orch.run("dangerous run")
    await op
    assert "executed: go" in result.output_text


@pytest.mark.asyncio
async def test_high_risk_tool_cancelled(tmp_path: Path) -> None:
    cfg = _make_cfg(tmp_path)
    bus = EventBus()
    plan = json.dumps(
        {
            "plan": [
                {
                    "id": "s1",
                    "description": "do dangerous thing",
                    "tool": "dangerous_demo",
                    "args": {"payload": "go"},
                    "depends_on": [],
                }
            ]
        }
    )
    provider = MockProvider(chat_response=plan)
    router = Router(cfg, {"mock": provider})  # type: ignore[arg-type]
    planner = Planner(router)
    tools = _registry()
    orch = Orchestrator(
        cfg, bus, planner, tools, agent_name="planner", hitl_timeout_s=2.0,
    )
    requests = bus.subscribe(REQUEST_TOPIC)

    async def operator() -> None:
        async for ev in requests:
            await bus.publish(
                Event(
                    RESPONSE_TOPIC,
                    {"request_id": ev.payload["request_id"], "approved": False, "reason": "test"},
                )
            )
            return

    op = asyncio.create_task(operator())
    with pytest.raises(HITLDenied):
        await orch.run("dangerous run")
    await op
