"""Append-only JSONL audit log writer."""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditEntry:
    agent: str
    action: str
    input_summary: str = ""
    output_summary: str = ""
    tokens: int = 0
    cost_usd: float = 0.0
    ts: float = field(default_factory=time.time)
    extra: dict[str, Any] = field(default_factory=dict)


class AuditLog:
    """Thread-safe append-only writer to a JSONL file."""

    def __init__(self, path: str | Path = "aisos.audit.log") -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def append(self, entry: AuditEntry) -> None:
        line = json.dumps(asdict(entry), ensure_ascii=False, sort_keys=True)
        with self._lock:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")

    def read_all(self) -> list[dict[str, Any]]:
        if not self._path.exists():
            return []
        with self._path.open("r", encoding="utf-8") as fh:
            return [json.loads(ln) for ln in fh if ln.strip()]


__all__ = ["AuditEntry", "AuditLog"]
