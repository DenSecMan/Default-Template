"""Tests for TUI slash command dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from aisos.orchestration.registry import AgentRegistry, AgentSpec
from aisos.tools.base import BaseTool
from aisos.tools.registry import ToolRegistry
from aisos.tui.commands import CommandContext, dispatch, is_command


class _In(BaseModel):
    pass


class _T(BaseTool):
    name = "demo"
    description = "demo tool"
    input_schema = _In
    risk_level = "low"

    async def run(self, input: _In) -> dict:  # type: ignore[override]
        return {}


@dataclass
class _FakeApp:
    written: list[str] = field(default_factory=list)
    quit_requested: bool = False

    def write_output(self, text: str) -> None:
        self.written.append(text)

    def request_quit(self) -> None:
        self.quit_requested = True


def _ctx() -> CommandContext:
    tools = ToolRegistry()
    tools.register(_T())
    agents = AgentRegistry()
    agents.register(AgentSpec(name="planner", description="d"))
    return CommandContext(app=_FakeApp(), tools=tools, agents=agents, cost=None)


def test_is_command_detects_slash() -> None:
    assert is_command("/help")
    assert not is_command("hello")


def test_help_lists_tools() -> None:
    ctx = _ctx()
    assert dispatch(ctx, "/help") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "demo" in out
    assert "/help" in out


def test_status_lists_agents() -> None:
    ctx = _ctx()
    assert dispatch(ctx, "/status") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "planner" in out


def test_quit_calls_app_quit() -> None:
    ctx = _ctx()
    assert dispatch(ctx, "/quit") is True
    assert ctx.app.quit_requested is True  # type: ignore[attr-defined]


def test_unknown_command_handled_gracefully() -> None:
    ctx = _ctx()
    assert dispatch(ctx, "/bogus") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "Unknown command" in out


def test_non_command_returns_false() -> None:
    ctx = _ctx()
    assert dispatch(ctx, "hello world") is False
