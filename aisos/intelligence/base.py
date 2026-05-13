"""Abstract LLM provider contract."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Sequence, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class BaseLLMProvider(ABC):
    """All LLM providers (Azure OpenAI, mocks, future) implement this."""

    name: str = "base"

    @abstractmethod
    async def chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> str:
        """Single-shot chat completion. Returns the assistant message text."""

    @abstractmethod
    def stream(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        """Streaming chat completion. Yields delta text chunks.

        Implementations return an `AsyncIterator[str]` directly (e.g. an async
        generator). Callers do `async for chunk in provider.stream(...)`.
        """

    @abstractmethod
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Batch embeddings. Returns one vector per text in order."""


__all__ = ["BaseLLMProvider", "ChatMessage"]
