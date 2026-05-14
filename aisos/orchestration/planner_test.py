"""Tests for orchestration.planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aisos.config import load_config
from aisos.intelligence.base_test import MockProvider
from aisos.intelligence.router import Router
from aisos.memory.db import get_connection
from aisos.memory.short_term import ShortTermMemory, Step
from aisos.orchestration.planner import Planner, parse_plan
from aisos.orchestration.state import AgentState


def test_parse_plan_accepts_valid_json() -> None:
    raw = json.dumps(
        {
            "plan": [
                {"id": "s1", "description": "first", "tool": "echo", "args": {"text": "hi"}, "depends_on": []},
                {"id": "s2", "description": "second", "tool": None, "args": {}, "depends_on": ["s1"]},
            ]
        }
    )
    nodes = parse_plan(raw)
    assert [n.id for n in nodes] == ["s1", "s2"]
    assert nodes[1].depends_on == ["s1"]


def test_parse_plan_strips_markdown_fence() -> None:
    raw = "```json\n" + json.dumps({"plan": [{"id": "x", "description": "y"}]}) + "\n```"
    nodes = parse_plan(raw)
    assert nodes[0].id == "x"


def test_parse_plan_rejects_bad_json() -> None:
    with pytest.raises(ValueError):
        parse_plan("not json")


def test_parse_plan_rejects_missing_plan_key() -> None:
    with pytest.raises(ValueError):
        parse_plan('{"other": []}')


def _make_router(tmp_path: Path, plan_json: str) -> tuple[Router, MockProvider]:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text('[routing]\nplan = { provider = "mock", model = "m" }\n', encoding="utf-8")
    cfg = load_config(env_file=env, toml_file=toml)
    mock = MockProvider(chat_response=plan_json)
    return Router(cfg, {"mock": mock}), mock  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_planner_node_invokes_router_and_parses(tmp_path: Path) -> None:
    plan_json = json.dumps({"plan": [{"id": "a", "description": "do"}]})
    router, _ = _make_router(tmp_path, plan_json)
    planner = Planner(router)
    state = await planner(AgentState(prompt="say hi"))
    assert len(state.plan) == 1
    assert state.plan[0].id == "a"


@pytest.mark.asyncio
async def test_planner_injects_history_between_system_and_prompt(tmp_path: Path) -> None:
    plan_json = json.dumps({"plan": [{"id": "a", "description": "do"}]})
    router, mock = _make_router(tmp_path, plan_json)

    conn = get_connection(tmp_path / "mem.db")
    stm = ShortTermMemory(conn)
    stm.append(Step(role="user", content="previous question"))
    stm.append(Step(role="assistant", content="previous answer"))

    planner = Planner(router, memory=stm)
    await planner(AgentState(prompt="current question"))

    msgs = mock.chat_calls[0]
    roles = [m["role"] for m in msgs]
    assert roles == ["system", "user", "assistant", "user"]
    assert msgs[1]["content"] == "previous question"
    assert msgs[2]["content"] == "previous answer"
    assert msgs[3]["content"] == "current question"
    conn.close()


@pytest.mark.asyncio
async def test_planner_with_no_memory_sends_system_then_prompt(tmp_path: Path) -> None:
    plan_json = json.dumps({"plan": [{"id": "a", "description": "do"}]})
    router, mock = _make_router(tmp_path, plan_json)
    planner = Planner(router)
    await planner(AgentState(prompt="hello"))
    msgs = mock.chat_calls[0]
    assert msgs[0]["role"] == "system"
    assert msgs[-1] == {"role": "user", "content": "hello"}
    assert len(msgs) == 2


@pytest.mark.asyncio
async def test_planner_respects_context_turns_limit(tmp_path: Path) -> None:
    plan_json = json.dumps({"plan": [{"id": "a", "description": "do"}]})
    router, mock = _make_router(tmp_path, plan_json)

    conn = get_connection(tmp_path / "mem.db")
    stm = ShortTermMemory(conn)
    for i in range(20):
        stm.append(Step(role="user", content=f"q{i}"))
        stm.append(Step(role="assistant", content=f"a{i}"))

    planner = Planner(router, memory=stm, context_turns=3)
    await planner(AgentState(prompt="final"))

    msgs = mock.chat_calls[0]
    # system + 3*2 history turns + 1 current = 8
    assert len(msgs) == 8
    assert msgs[-1]["content"] == "final"
    conn.close()
