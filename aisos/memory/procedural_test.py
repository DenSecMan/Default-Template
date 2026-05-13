"""Tests for memory.procedural recipe CRUD."""

from __future__ import annotations

from pathlib import Path

from aisos.memory.db import get_connection
from aisos.memory.procedural import ProceduralMemory


def test_save_and_load(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "p.db")
    pm = ProceduralMemory(conn)
    saved = pm.save_recipe("greet", {"steps": ["echo hello"]})
    assert saved.name == "greet"
    loaded = pm.load_recipe("greet")
    assert loaded is not None
    assert loaded.plan == {"steps": ["echo hello"]}
    conn.close()


def test_save_overwrites_existing_and_bumps_updated_at(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "p.db")
    pm = ProceduralMemory(conn)
    first = pm.save_recipe("r", {"v": 1})
    second = pm.save_recipe("r", {"v": 2})
    assert second.plan == {"v": 2}
    assert second.updated_at >= first.updated_at
    conn.close()


def test_list_and_delete(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "p.db")
    pm = ProceduralMemory(conn)
    pm.save_recipe("a", {})
    pm.save_recipe("b", {})
    names = [r.name for r in pm.list_recipes()]
    assert names == ["a", "b"]
    assert pm.delete_recipe("a") is True
    assert pm.delete_recipe("missing") is False
    assert [r.name for r in pm.list_recipes()] == ["b"]
    conn.close()


def test_load_missing_returns_none(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "p.db")
    pm = ProceduralMemory(conn)
    assert pm.load_recipe("nope") is None
    conn.close()
