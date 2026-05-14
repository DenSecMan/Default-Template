"""Tests for TUI slash command dispatcher."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pytest
from pydantic import BaseModel

from aisos.memory.db import get_connection
from aisos.memory.procedural import ProceduralMemory
from aisos.memory.short_term import ShortTermMemory, Step
from aisos.observability.audit_log import AuditLog
from aisos.orchestration.registry import AgentRegistry, AgentSpec
from aisos.tools.base import BaseTool
from aisos.tools.registry import ToolRegistry
from aisos.tui.commands import CommandContext, dispatch, is_command, list_commands


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


def test_list_commands_returns_pairs_with_descriptions() -> None:
    pairs = list_commands()
    names = [n for n, _ in pairs]
    assert "help" in names
    assert "status" in names
    assert "memory" in names
    assert "export" in names
    assert "quit" in names
    # every command must have a description
    assert all(desc for _, desc in pairs)


def test_memory_no_stores_connected() -> None:
    ctx = _ctx()
    assert dispatch(ctx, "/memory") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "not connected" in out


def test_memory_shows_short_term_history(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    stm = ShortTermMemory(conn)
    stm.append(Step(role="user", content="check ip 1.2.3.4"))
    stm.append(Step(role="assistant", content="Here are the results…"))

    ctx = _ctx()
    ctx.short_term = stm
    ctx.db_conn = conn
    assert dispatch(ctx, "/memory") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "Short-term" in out
    assert "2 turns" in out
    assert "check ip 1.2.3.4" in out
    conn.close()


def test_memory_shows_procedural_recipes(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    pm = ProceduralMemory(conn)
    pm.save_recipe("triage-ip", {"steps": ["check vt", "check abuseipdb"]})

    ctx = _ctx()
    ctx.procedural = pm
    ctx.db_conn = conn
    assert dispatch(ctx, "/memory") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "Procedural" in out
    assert "triage-ip" in out
    assert "1 recipe" in out
    conn.close()


def test_memory_shows_all_three_sections(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    stm = ShortTermMemory(conn)
    stm.append(Step(role="user", content="hello"))
    pm = ProceduralMemory(conn)
    pm.save_recipe("my-playbook", {"steps": []})

    ctx = _ctx()
    ctx.short_term = stm
    ctx.procedural = pm
    ctx.db_conn = conn
    assert dispatch(ctx, "/memory") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "Short-term" in out
    assert "Semantic" in out
    assert "Procedural" in out
    conn.close()


# ---------------------------------------------------------------------------
# /export tests
# ---------------------------------------------------------------------------

def test_export_creates_markdown_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    ctx = _ctx()
    assert dispatch(ctx, "/export") is True
    out = "\n".join(ctx.app.written)  # type: ignore[attr-defined]
    assert "Report saved" in out
    reports = list(tmp_path.glob("aisos-report-*.md"))
    assert len(reports) == 1
    content = reports[0].read_text(encoding="utf-8")
    assert "AISOS Investigation Report" in content


def test_export_includes_conversation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    conn = get_connection(tmp_path / "m.db")
    stm = ShortTermMemory(conn)
    stm.append(Step(role="user", content="check this IP"))
    stm.append(Step(role="assistant", content="Here are the results"))

    ctx = _ctx()
    ctx.short_term = stm
    assert dispatch(ctx, "/export") is True

    reports = list(tmp_path.glob("aisos-report-*.md"))
    content = reports[0].read_text(encoding="utf-8")
    assert "check this IP" in content
    assert "Here are the results" in content
    conn.close()


def test_export_includes_audit_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    log_path = tmp_path / "aisos.audit.log"
    audit = AuditLog(log_path)
    from aisos.observability.audit_log import AuditEntry
    audit.append(AuditEntry(agent="default", action="echo", input_summary="hi", output_summary="hi"))

    ctx = _ctx()
    ctx.audit = audit
    assert dispatch(ctx, "/export") is True

    reports = list(tmp_path.glob("aisos-report-*.md"))
    content = reports[0].read_text(encoding="utf-8")
    assert "echo" in content
    assert "Tool Calls" in content
