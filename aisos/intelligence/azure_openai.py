"""Azure OpenAI concrete LLM provider."""

from __future__ import annotations

from typing import Any, AsyncIterator, Sequence

from openai import AsyncAzureOpenAI

from aisos.config import AppConfig
from aisos.intelligence.base import BaseLLMProvider, ChatMessage


class AzureOpenAIProvider(BaseLLMProvider):
    name = "azure_openai"

    def __init__(self, config: AppConfig, client: AsyncAzureOpenAI | None = None) -> None:
        self._config = config
        self._client = client or AsyncAzureOpenAI(
            azure_endpoint=config.settings.azure_openai_endpoint,
            api_key=config.settings.azure_openai_api_key,
            api_version=config.settings.azure_openai_api_version,
        )
        self._chat_deployment = config.settings.azure_openai_deployment_chat
        self._embed_deployment = config.settings.azure_openai_deployment_embed

    async def chat(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> str:
        model = kwargs.pop("model", None) or self._chat_deployment
        resp = await self._client.chat.completions.create(
            model=model, messages=list(messages), stream=False, **kwargs
        )
        return resp.choices[0].message.content or ""

    async def stream(
        self, messages: Sequence[ChatMessage], **kwargs: Any
    ) -> AsyncIterator[str]:
        model = kwargs.pop("model", None) or self._chat_deployment
        resp = await self._client.chat.completions.create(
            model=model, messages=list(messages), stream=True, **kwargs
        )
        async for chunk in resp:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.embeddings.create(
            model=self._embed_deployment, input=list(texts)
        )
        return [d.embedding for d in resp.data]


__all__ = ["AzureOpenAIProvider"]
