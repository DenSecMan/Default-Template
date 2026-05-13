"""Tests for memory.db connection + migrations."""

from __future__ import annotations

from pathlib import Path

from aisos.memory.db import _MIGRATIONS, get_connection


def test_migrations_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "x.db"
    c1 = get_connection(db)
    c1.close()
    c2 = get_connection(db)
    cur = c2.execute("SELECT MAX(version) AS v FROM schema_version;")
    assert cur.fetchone()["v"] == max(v for v, _ in _MIGRATIONS)
    c2.close()


def test_wal_enabled(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "y.db")
    cur = conn.execute("PRAGMA journal_mode;")
    assert cur.fetchone()[0].lower() == "wal"
    conn.close()


def test_vec_table_present(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "z.db")
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE name='vec_embeddings';"
    )
    assert cur.fetchone() is not None
    conn.close()
