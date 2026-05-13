"""Slash command dispatcher for the TUI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from aisos.observability.cost_tracker import CostTracker
from aisos.orchestration.registry import AgentRegistry
from aisos.tools.registry import ToolRegistry


class _AppLike(Protocol):
    def write_output(self, text: str) -> None: ...
    def request_quit(self) -> None: ...


@dataclass
class CommandContext:
    app: _AppLike
    tools: ToolRegistry
    agents: AgentRegistry
    cost: CostTracker | None = None


CommandFn = Callable[[CommandContext, list[str]], None]


def _cmd_help(ctx: CommandContext, args: list[str]) -> None:
    lines = [
        "Available commands:",
        "  /help    — show this help",
        "  /status  — agents + session cost",
        "  /quit    — exit",
        "",
        "Registered tools:",
    ]
    for t in ctx.tools.all():
        lines.append(f"  - {t.name} ({t.risk_level}) — {t.description}")
    ctx.app.write_output("\n".join(lines))


def _cmd_status(ctx: CommandContext, args: list[str]) -> None:
    lines = ["Agents:"]
    for spec in ctx.agents.all() or []:
        lines.append(f"  - {spec.name}: {spec.description}")
    if ctx.cost is not None:
        s = ctx.cost.summary()
        lines.append("")
        lines.append(f"Session cost: ${s.total.usd:.4f}")
        lines.append(
            f"  tokens in/out: {s.total.in_tokens}/{s.total.out_tokens}"
        )
    ctx.app.write_output("\n".join(lines))


def _cmd_quit(ctx: CommandContext, args: list[str]) -> None:
    ctx.app.request_quit()


COMMANDS: dict[str, CommandFn] = {
    "help": _cmd_help,
    "status": _cmd_status,
    "quit": _cmd_quit,
    "exit": _cmd_quit,
}


def is_command(text: str) -> bool:
    return text.startswith("/")


def dispatch(ctx: CommandContext, text: str) -> bool:
    """Run the slash command. Returns True if handled, False otherwise."""
    if not is_command(text):
        return False
    parts = text[1:].strip().split()
    if not parts:
        return False
    name, *args = parts
    fn = COMMANDS.get(name.lower())
    if fn is None:
        ctx.app.write_output(f"Unknown command: /{name}. Try /help.")
        return True
    fn(ctx, args)
    return True


__all__ = ["COMMANDS", "CommandContext", "dispatch", "is_command"]
