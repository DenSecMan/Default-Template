"""Tests for token counting & trim semantics."""

from __future__ import annotations

from aisos.intelligence.base import ChatMessage
from aisos.intelligence.token_controller import (
    count_messages,
    count_tokens,
    trim,
)


def test_count_tokens_nonzero() -> None:
    assert count_tokens("hello world", "gpt-4o") > 0


def test_trim_no_op_when_under_budget() -> None:
    msgs: list[ChatMessage] = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi"},
    ]
    out = trim(msgs, max_tokens=10_000, model="gpt-4o")
    assert out == msgs


def test_trim_evicts_oldest_non_system() -> None:
    msgs: list[ChatMessage] = [
        {"role": "system", "content": "S"},
        {"role": "user", "content": "old " * 100},
        {"role": "assistant", "content": "older " * 100},
        {"role": "user", "content": "fresh"},
    ]
    out = trim(msgs, max_tokens=count_messages([msgs[0], msgs[3]], "gpt-4o") + 1, model="gpt-4o")
    assert out[0]["role"] == "system"
    assert out[-1]["content"] == "fresh"
    assert all(m["content"] != "old " * 100 for m in out)


def test_trim_keeps_system_even_when_tight() -> None:
    msgs: list[ChatMessage] = [
        {"role": "system", "content": "system text"},
        {"role": "user", "content": "u1 " * 50},
        {"role": "user", "content": "u2 " * 50},
    ]
    out = trim(msgs, max_tokens=20, model="gpt-4o")
    assert any(m["role"] == "system" for m in out)
