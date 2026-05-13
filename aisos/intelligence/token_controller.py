"""Token counting + message truncation via tiktoken."""

from __future__ import annotations

from typing import Sequence

import tiktoken

from aisos.intelligence.base import ChatMessage

_DEFAULT_ENCODING = "cl100k_base"


def _encoding_for(model: str) -> tiktoken.Encoding:
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        return tiktoken.get_encoding(_DEFAULT_ENCODING)


def count_tokens(text: str, model: str = "gpt-4o") -> int:
    """Return the token count for `text` under `model`'s encoding."""
    return len(_encoding_for(model).encode(text))


def count_messages(messages: Sequence[ChatMessage], model: str = "gpt-4o") -> int:
    """Approximate chat-formatted token count: per-message overhead + content."""
    enc = _encoding_for(model)
    per_message_overhead = 4  # role + separators (OpenAI heuristic)
    total = 0
    for m in messages:
        total += per_message_overhead
        total += len(enc.encode(m.get("role", "")))
        total += len(enc.encode(m.get("content", "")))
    total += 2  # priming for assistant reply
    return total


def trim(
    messages: Sequence[ChatMessage],
    max_tokens: int,
    model: str = "gpt-4o",
) -> list[ChatMessage]:
    """Drop oldest non-system messages until total token count fits max_tokens."""
    msgs = list(messages)
    if count_messages(msgs, model) <= max_tokens:
        return msgs
    system_idx = [i for i, m in enumerate(msgs) if m.get("role") == "system"]
    keep_system = {i: msgs[i] for i in system_idx}
    non_system = [(i, m) for i, m in enumerate(msgs) if i not in keep_system]
    while non_system and count_messages(
        [m for _, m in sorted(list(keep_system.items()) + non_system, key=lambda x: x[0])],
        model,
    ) > max_tokens:
        non_system.pop(0)
    final = sorted(list(keep_system.items()) + non_system, key=lambda x: x[0])
    return [m for _, m in final]


__all__ = ["count_messages", "count_tokens", "trim"]
