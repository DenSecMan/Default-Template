"""Tests for Orchestrator: parallel execution, inject_steps, auto-embed."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from aisos.config import load_config
from aisos.intelligence.base_test import MockProvider
from aisos.intelligence.router import Router
from aisos.orchestration.event_bus import EventBus
from aisos.orchestration.orchestrator import Orchestrator
from aisos.orchestration.planner import Planner
from aisos.orchestration.state import StepNode
from aisos.tools.base import BaseTool
from aisos.tools.registry import ToolRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _In(BaseModel):
    value: str = ""


class _RecordingTool(BaseTool):
    """Records invocations so tests can verify order / parallelism."""
    name = "recorder"
    description = "test"
    input_schema = _In
    risk_level = "low"
    required_scope = "read"

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def run(self, input: _In) -> dict[str, Any]:  # type: ignore[override]
        self.calls.append(input.value)
        return {"recorded": input.value}


class _InjectTool(BaseTool):
    """Returns inject_steps in its result."""
    name = "inject_tool"
    description = "injects steps"
    input_schema = _In
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: _In) -> dict[str, Any]:  # type: ignore[override]
        return {
            "inject_steps": [
                {"id": "injected_1", "description": "injected", "tool": "recorder",
                 "args": {"value": "from_injection"}, "depends_on": []},
            ],
            "text": "playbook started",
        }


def _make_cfg(tmp_path: Path, plan_json: str) -> tuple[Any, MockProvider]:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[routing]\nplan = { provider = "mock", model = "m" }\n'
        '[rbac]\ndefault = ["read"]\n',
        encoding="utf-8",
    )
    cfg = load_config(env_file=env, toml_file=toml)
    mock = MockProvider(chat_response=plan_json)
    return cfg, mock


def _orch(tmp_path: Path, plan_json: str, tools: ToolRegistry) -> Orchestrator:
    cfg, mock = _make_cfg(tmp_path, plan_json)
    router = Router(cfg, {"mock": mock})  # type: ignore[arg-type]
    planner = Planner(router)
    bus = EventBus()
    return Orchestrator(cfg, bus, planner, tools, agent_name="default")


# ---------------------------------------------------------------------------
# Parallel execution
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_independent_steps_both_execute(tmp_path: Path) -> None:
    recorder = _RecordingTool()
    tools = ToolRegistry()
    tools.register(recorder)

    plan = {"plan": [
        {"id": "s1", "description": "first",  "tool": "recorder", "args": {"value": "A"}, "depends_on": []},
        {"id": "s2", "description": "second", "tool": "recorder", "args": {"value": "B"}, "depends_on": []},
    ]}
    orch = _orch(tmp_path, json.dumps(plan), tools)
    result = await orch.run("do both")

    assert set(recorder.calls) == {"A", "B"}
    assert result.state.results["s1"] == {"recorded": "A"}
    assert result.state.results["s2"] == {"recorded": "B"}


@pytest.mark.asyncio
async def test_dependent_steps_run_in_order(tmp_path: Path) -> None:
    recorder = _RecordingTool()
    tools = ToolRegistry()
    tools.register(recorder)

    plan = {"plan": [
        {"id": "s1", "description": "first",  "tool": "recorder", "args": {"value": "first"},  "depends_on": []},
        {"id": "s2", "description": "second", "tool": "recorder", "args": {"value": "second"}, "depends_on": ["s1"]},
        {"id": "s3", "description": "third",  "tool": "recorder", "args": {"value": "third"},  "depends_on": ["s2"]},
    ]}
    orch = _orch(tmp_path, json.dumps(plan), tools)
    await orch.run("chain")

    assert recorder.calls == ["first", "second", "third"]


@pytest.mark.asyncio
async def test_diamond_dag_executes_all_nodes(tmp_path: Path) -> None:
    recorder = _RecordingTool()
    tools = ToolRegistry()
    tools.register(recorder)

    # A -> [B, C] -> D
    plan = {"plan": [
        {"id": "A", "description": "root",  "tool": "recorder", "args": {"value": "A"}, "depends_on": []},
        {"id": "B", "description": "left",  "tool": "recorder", "args": {"value": "B"}, "depends_on": ["A"]},
        {"id": "C", "description": "right", "tool": "recorder", "args": {"value": "C"}, "depends_on": ["A"]},
        {"id": "D", "description": "join",  "tool": "recorder", "args": {"value": "D"}, "depends_on": ["B", "C"]},
    ]}
    orch = _orch(tmp_path, json.dumps(plan), tools)
    await orch.run("diamond")

    assert recorder.calls[0] == "A"
    assert set(recorder.calls[1:3]) == {"B", "C"}
    assert recorder.calls[3] == "D"


# ---------------------------------------------------------------------------
# inject_steps (playbook expansion)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inject_steps_are_executed(tmp_path: Path) -> None:
    recorder = _RecordingTool()
    inject = _InjectTool()
    tools = ToolRegistry()
    tools.register(recorder)
    tools.register(inject)

    plan = {"plan": [
        {"id": "pb", "description": "run playbook", "tool": "inject_tool",
         "args": {}, "depends_on": []},
    ]}
    orch = _orch(tmp_path, json.dumps(plan), tools)
    result = await orch.run("run it")

    assert "from_injection" in recorder.calls
    assert "injected_1" in result.state.results


# ---------------------------------------------------------------------------
# Auto-embed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_embed_called_for_tool_steps(tmp_path: Path) -> None:
    recorder = _RecordingTool()
    tools = ToolRegistry()
    tools.register(recorder)

    plan = {"plan": [
        {"id": "s1", "description": "step", "tool": "recorder",
         "args": {"value": "x"}, "depends_on": []},
    ]}
    cfg, mock = _make_cfg(tmp_path, json.dumps(plan))
    router = Router(cfg, {"mock": mock})  # type: ignore[arg-type]
    planner = Planner(router)
    bus = EventBus()

    semantic = MagicMock()
    semantic.add = AsyncMock(return_value=1)

    orch = Orchestrator(cfg, bus, planner, tools, agent_name="default", semantic=semantic)
    await orch.run("embed test")

    # Drain background tasks so create_task callbacks fire
    await asyncio.gather(*asyncio.all_tasks() - {asyncio.current_task()},
                         return_exceptions=True)

    semantic.add.assert_called_once()
    call_text = semantic.add.call_args[0][0]
    assert "recorder" in call_text


@pytest.mark.asyncio
async def test_auto_embed_not_called_for_noop_steps(tmp_path: Path) -> None:
    tools = ToolRegistry()

    plan = {"plan": [
        {"id": "s1", "description": "just answer", "tool": None,
         "args": {}, "depends_on": []},
    ]}
    cfg, mock = _make_cfg(tmp_path, json.dumps(plan))
    router = Router(cfg, {"mock": mock})  # type: ignore[arg-type]
    planner = Planner(router)
    bus = EventBus()

    semantic = MagicMock()
    semantic.add = AsyncMock(return_value=1)

    orch = Orchestrator(cfg, bus, planner, tools, agent_name="default", semantic=semantic)
    await orch.run("noop test")

    semantic.add.assert_not_called()
