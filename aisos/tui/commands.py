"""Slash command dispatcher for the TUI."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Protocol

from aisos.memory.procedural import ProceduralMemory
from aisos.memory.short_term import ShortTermMemory
from aisos.observability.audit_log import AuditLog
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
    short_term: ShortTermMemory | None = None
    procedural: ProceduralMemory | None = None
    db_conn: sqlite3.Connection | None = None
    audit: AuditLog | None = None


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


def _cmd_memory(ctx: CommandContext, args: list[str]) -> None:
    sections: list[str] = []

    if ctx.short_term is not None:
        history = ctx.short_term.history()
        n = len(history)
        block = [f"Short-term ({n} turn{'s' if n != 1 else ''} this session)"]
        if history:
            for step in history[-8:]:
                preview = step.content[:100].replace("\n", " ")
                suffix = "…" if len(step.content) > 100 else ""
                block.append(f"  [{step.role}] {preview}{suffix}")
            if n > 8:
                block.append(f"  … and {n - 8} earlier turn{'s' if n - 8 != 1 else ''}")
        else:
            block.append("  (empty)")
        sections.append("\n".join(block))

    if ctx.db_conn is not None:
        try:
            total = ctx.db_conn.execute(
                "SELECT COUNT(*) AS n FROM vec_embeddings_meta;"
            ).fetchone()["n"]
            rows = ctx.db_conn.execute(
                "SELECT text, datetime(created_at, 'unixepoch') AS ts "
                "FROM vec_embeddings_meta ORDER BY created_at DESC LIMIT 5;"
            ).fetchall()
            block = [f"Semantic ({total} embedding{'s' if total != 1 else ''} stored)"]
            if rows:
                for row in rows:
                    preview = row["text"][:100].replace("\n", " ")
                    suffix = "…" if len(row["text"]) > 100 else ""
                    block.append(f"  [{row['ts']}] {preview}{suffix}")
                if total > 5:
                    block.append(f"  … and {total - 5} more")
            else:
                block.append("  (empty — nothing embedded yet)")
        except Exception as exc:
            block = [f"Semantic\n  (unavailable: {exc})"]
        sections.append("\n".join(block))

    if ctx.procedural is not None:
        recipes = ctx.procedural.list_recipes()
        n = len(recipes)
        block = [f"Procedural ({n} recipe{'s' if n != 1 else ''} saved)"]
        if recipes:
            for r in recipes:
                block.append(f"  {r.name}")
        else:
            block.append("  (empty — no playbooks saved yet)")
        sections.append("\n".join(block))

    if not sections:
        ctx.app.write_output("Memory stores not connected.")
        return

    ctx.app.write_output("\n\n".join(sections))


def _cmd_export(ctx: CommandContext, args: list[str]) -> None:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"aisos-report-{ts}.md"

    lines: list[str] = [
        f"# AISOS Investigation Report",
        f"",
        f"Exported: {datetime.now().isoformat(timespec='seconds')}",
        f"",
    ]

    if ctx.short_term is not None:
        history = ctx.short_term.history()
        lines += ["## Conversation", ""]
        if history:
            for step in history:
                lines.append(f"**{step.role.title()}:** {step.content}")
                lines.append("")
        else:
            lines += ["_(empty)_", ""]

    if ctx.audit is not None:
        entries = ctx.audit.read_all()
        lines += ["## Tool Calls", ""]
        if entries:
            for e in entries:
                ts_str = datetime.fromtimestamp(e.get("ts", 0)).strftime("%H:%M:%S")
                lines.append(f"- `{e.get('action', '?')}` ({e.get('agent', '?')}) @ {ts_str}")
                lines.append(f"  - Input: {e.get('input_summary', '')}")
                lines.append(f"  - Output: {e.get('output_summary', '')}")
        else:
            lines += ["_(no tool calls recorded)_", ""]
        lines.append("")

    if ctx.cost is not None:
        s = ctx.cost.summary()
        lines += [
            "## Session Cost",
            "",
            f"| | Tokens in | Tokens out | USD |",
            f"|---|---|---|---|",
            f"| **Total** | {s.total.in_tokens} | {s.total.out_tokens} | ${s.total.usd:.4f} |",
        ]
        for model, bucket in s.per_model.items():
            lines.append(
                f"| {model} | {bucket.in_tokens} | {bucket.out_tokens} | ${bucket.usd:.4f} |"
            )
        lines.append("")

    try:
        Path(filename).write_text("\n".join(lines), encoding="utf-8")
        ctx.app.write_output(f"Report saved → {filename}")
    except OSError as exc:
        ctx.app.write_output(f"Export failed: {exc}")


COMMANDS: dict[str, CommandFn] = {
    "help": _cmd_help,
    "status": _cmd_status,
    "memory": _cmd_memory,
    "export": _cmd_export,
    "quit": _cmd_quit,
    "exit": _cmd_quit,
}

DESCRIPTIONS: dict[str, str] = {
    "help": "Show available commands and registered tools",
    "status": "Show agents and session cost",
    "memory": "Show short-term history, semantic embeddings, and saved playbooks",
    "export": "Save the session conversation, tool calls, and cost to a markdown report",
    "quit": "Exit AISOS",
    "exit": "Exit AISOS",
}


def list_commands() -> list[tuple[str, str]]:
    """Return (name, description) pairs in stable display order."""
    return [(name, DESCRIPTIONS.get(name, "")) for name in COMMANDS]


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


__all__ = [
    "COMMANDS",
    "CommandContext",
    "DESCRIPTIONS",
    "dispatch",
    "is_command",
    "list_commands",
]
