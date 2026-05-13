"""Short-term working memory: in-memory deque + checkpoint to SQLite."""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Step:
    """One unit of conversation/agent history."""

    role: str
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)


class ShortTermMemory:
    """Bounded in-memory history with SQLite checkpointing."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        session_id: str | None = None,
        max_steps: int = 100,
    ) -> None:
        self._conn = conn
        self.session_id = session_id or uuid.uuid4().hex
        self._buffer: deque[Step] = deque(maxlen=max_steps)
        self._ensure_session()

    def _ensure_session(self) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO sessions(id, created_at, metadata) VALUES (?, ?, ?);",
                (self.session_id, time.time(), None),
            )

    def append(self, step: Step) -> None:
        self._buffer.append(step)

    def history(self) -> list[Step]:
        return list(self._buffer)

    def clear(self) -> None:
        self._buffer.clear()

    def checkpoint(self) -> int:
        """Persist current buffer as one snapshot row. Returns the snapshot id."""
        payload = json.dumps([asdict(s) for s in self._buffer], ensure_ascii=False)
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO short_term_snapshots(session_id, created_at, payload) VALUES (?, ?, ?);",
                (self.session_id, time.time(), payload),
            )
        return int(cur.lastrowid or 0)

    def restore(self, snapshot_id: int | None = None) -> list[Step]:
        """Reload buffer from a snapshot (latest if id=None)."""
        if snapshot_id is None:
            cur = self._conn.execute(
                "SELECT payload FROM short_term_snapshots WHERE session_id=? "
                "ORDER BY id DESC LIMIT 1;",
                (self.session_id,),
            )
        else:
            cur = self._conn.execute(
                "SELECT payload FROM short_term_snapshots WHERE id=?;", (snapshot_id,)
            )
        row = cur.fetchone()
        if row is None:
            return []
        rows = json.loads(row["payload"])
        self._buffer.clear()
        for r in rows:
            self._buffer.append(Step(**r))
        return list(self._buffer)


__all__ = ["ShortTermMemory", "Step"]
