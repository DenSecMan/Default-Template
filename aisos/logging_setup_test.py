"""Tests for aisos.logging_setup."""

from __future__ import annotations

import io
import json
import logging

from aisos.logging_setup import (
    JsonFormatter,
    bind_context,
    configure_logging,
    reset_context,
)


def test_json_formatter_emits_required_fields() -> None:
    fmt = JsonFormatter()
    record = logging.LogRecord(
        name="t", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    payload = json.loads(fmt.format(record))
    assert payload["level"] == "INFO"
    assert payload["logger"] == "t"
    assert payload["msg"] == "hello world"
    assert "ts" in payload


def test_context_filter_injects_fields() -> None:
    logger = configure_logging("DEBUG")
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    handler.setFormatter(JsonFormatter())
    from aisos.logging_setup import _ContextFilter
    handler.addFilter(_ContextFilter())
    logger.addHandler(handler)
    try:
        prev = bind_context(agent_name="planner", thread_id="abc")
        try:
            logger.info("decided")
        finally:
            reset_context(prev)
        line = buf.getvalue().strip().splitlines()[-1]
        payload = json.loads(line)
        assert payload["agent_name"] == "planner"
        assert payload["thread_id"] == "abc"
    finally:
        logger.removeHandler(handler)


def test_configure_logging_is_idempotent() -> None:
    a = configure_logging()
    b = configure_logging()
    assert a is b
    json_handlers = [h for h in a.handlers if getattr(h, "_aisos_json", False)]
    assert len(json_handlers) == 1
