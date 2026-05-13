"""Tests for memory.short_term."""

from __future__ import annotations

from pathlib import Path

from aisos.memory.db import get_connection
from aisos.memory.short_term import ShortTermMemory, Step


def test_snapshot_round_trip(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "s.db")
    mem = ShortTermMemory(conn, session_id="sess1")
    mem.append(Step(role="user", content="hello"))
    mem.append(Step(role="assistant", content="hi", metadata={"tokens": 1}))
    snap_id = mem.checkpoint()
    assert snap_id > 0

    mem2 = ShortTermMemory(conn, session_id="sess1")
    restored = mem2.restore()
    assert [s.content for s in restored] == ["hello", "hi"]
    assert restored[1].metadata == {"tokens": 1}
    conn.close()


def test_buffer_max_steps_evicts_oldest(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "s.db")
    mem = ShortTermMemory(conn, max_steps=3)
    for i in range(5):
        mem.append(Step(role="user", content=str(i)))
    assert [s.content for s in mem.history()] == ["2", "3", "4"]
    conn.close()
