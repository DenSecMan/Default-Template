"""Tests for audit log."""

from __future__ import annotations

from pathlib import Path

from aisos.observability.audit_log import AuditEntry, AuditLog


def test_append_and_read(tmp_path: Path) -> None:
    log = AuditLog(tmp_path / "a.log")
    log.append(AuditEntry(agent="planner", action="run", tokens=10, cost_usd=0.01))
    log.append(AuditEntry(agent="planner", action="done", tokens=5, cost_usd=0.005))
    rows = log.read_all()
    assert [r["action"] for r in rows] == ["run", "done"]


def test_append_is_append_only(tmp_path: Path) -> None:
    p = tmp_path / "b.log"
    log1 = AuditLog(p)
    log1.append(AuditEntry(agent="a", action="x"))
    log2 = AuditLog(p)
    log2.append(AuditEntry(agent="a", action="y"))
    rows = AuditLog(p).read_all()
    assert [r["action"] for r in rows] == ["x", "y"]
