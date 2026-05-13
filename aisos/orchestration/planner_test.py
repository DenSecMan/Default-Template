"""Tests for orchestration.planner."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aisos.config import load_config
from aisos.intelligence.base_test import MockProvider
from aisos.intelligence.router import Router
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


@pytest.mark.asyncio
async def test_planner_node_invokes_router_and_parses(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[routing]\n'
        'plan = { provider = "mock", model = "m" }\n',
        encoding="utf-8",
    )
    cfg = load_config(env_file=env, toml_file=toml)
    plan_json = json.dumps({"plan": [{"id": "a", "description": "do"}]})
    router = Router(cfg, {"mock": MockProvider(chat_response=plan_json)})  # type: ignore[arg-type]
    planner = Planner(router)
    state = await planner(AgentState(prompt="say hi"))
    assert len(state.plan) == 1
    assert state.plan[0].id == "a"
