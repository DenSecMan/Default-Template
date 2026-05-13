"""Structured JSON logging with contextual fields."""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

_context: ContextVar[dict[str, Any]] = ContextVar("aisos_log_context", default={})


def bind_context(**kwargs: Any) -> dict[str, Any]:
    """Merge new fields into the per-task log context. Returns the previous context for restoration."""
    prev = _context.get()
    _context.set({**prev, **kwargs})
    return prev


def reset_context(prev: dict[str, Any]) -> None:
    _context.set(prev)


class _ContextFilter(logging.Filter):
    """Inject contextvar fields onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _context.get()
        for key, value in ctx.items():
            setattr(record, key, value)
        return True


class JsonFormatter(logging.Formatter):
    """Render records as single-line JSON."""

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in self._RESERVED or key.startswith("_"):
                continue
            if key in payload:
                continue
            try:
                json.dumps(value)
                payload[key] = value
            except TypeError:
                payload[key] = repr(value)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int | str = "INFO") -> logging.Logger:
    """Idempotently configure the root logger for JSON output to stderr."""
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        if getattr(handler, "_aisos_json", False):
            return root

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(_ContextFilter())
    handler._aisos_json = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    return root


__all__ = [
    "JsonFormatter",
    "bind_context",
    "configure_logging",
    "reset_context",
]
