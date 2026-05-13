"""Mock provider + smoke test for streaming contract."""

from __future__ import annotations

from typing import Any, AsyncIterator, Sequence

import pytest

from aisos.intelligence.base import BaseLLMProvider, ChatMessage


class MockProvider(BaseLLMProvider):
    """Reusable test double — also exported for downstream tests."""

    name = "mock"

    def __init__(
        self,
        chat_response: str = "ok",
        stream_chunks: Sequence[str] = ("hel", "lo"),
        embed_dim: int = 1536,
    ) -> None:
        self.chat_response = chat_response
        self.stream_chunks = list(stream_chunks)
        self.embed_dim = embed_dim
        self.chat_calls: list[list[ChatMessage]] = []
        self.embed_calls: list[list[str]] = []

    async def chat(self, messages: Sequence[ChatMessage], **kwargs: Any) -> str:
        self.chat_calls.append(list(messages))
        return self.chat_response

    async def stream(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        for chunk in self.stream_chunks:
            yield chunk

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.embed_calls.append(list(texts))
        return [[0.0] * self.embed_dim for _ in texts]


@pytest.mark.asyncio
async def test_mock_chat_records_messages() -> None:
    p = MockProvider(chat_response="hi")
    out = await p.chat([{"role": "user", "content": "ping"}])
    assert out == "hi"
    assert p.chat_calls == [[{"role": "user", "content": "ping"}]]


@pytest.mark.asyncio
async def test_mock_stream_yields_chunks() -> None:
    p = MockProvider(stream_chunks=["a", "b", "c"])
    chunks = [c async for c in p.stream([{"role": "user", "content": "x"}])]
    assert chunks == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_mock_embed_returns_one_per_input() -> None:
    p = MockProvider(embed_dim=4)
    out = await p.embed(["a", "b"])
    assert len(out) == 2
    assert all(len(v) == 4 for v in out)
