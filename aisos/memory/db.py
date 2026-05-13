"""SQLite connection manager with WAL + sqlite-vec extension + schema migrations."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

import sqlite_vec

_MIGRATIONS: tuple[tuple[int, str], ...] = (
    (1, """
        CREATE TABLE IF NOT EXISTS sessions (
            id          TEXT PRIMARY KEY,
            created_at  REAL NOT NULL,
            metadata    TEXT
        );

        CREATE TABLE IF NOT EXISTS short_term_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            created_at  REAL NOT NULL,
            payload     TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_snap_session
            ON short_term_snapshots(session_id, created_at);

        CREATE TABLE IF NOT EXISTS recipes (
            name       TEXT PRIMARY KEY,
            plan_json  TEXT NOT NULL,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS audit_log_index (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            ts          REAL NOT NULL,
            agent       TEXT,
            action      TEXT,
            offset_pos  INTEGER NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log_index(ts);
    """),
    (2, """
        CREATE VIRTUAL TABLE IF NOT EXISTS vec_embeddings USING vec0(
            embedding float[1536]
        );

        CREATE TABLE IF NOT EXISTS vec_embeddings_meta (
            rowid      INTEGER PRIMARY KEY,
            text       TEXT NOT NULL,
            metadata   TEXT,
            created_at REAL NOT NULL
        );
    """),
)


def _enable_vec(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)


def get_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a connection at db_path, enable WAL, load sqlite-vec, run migrations."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    _enable_vec(conn)
    _migrate(conn, _MIGRATIONS)
    return conn


def _migrate(conn: sqlite3.Connection, migrations: Iterable[tuple[int, str]]) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY);"
    )
    cur = conn.execute("SELECT MAX(version) AS v FROM schema_version;")
    row = cur.fetchone()
    current = row["v"] if row and row["v"] is not None else 0
    for version, sql in migrations:
        if version <= current:
            continue
        with conn:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_version(version) VALUES (?);", (version,)
            )


__all__ = ["get_connection"]
