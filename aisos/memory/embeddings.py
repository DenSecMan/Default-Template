"""Azure OpenAI embedding client (text-embedding-3-small, 1536 dim)."""

from __future__ import annotations

from typing import Sequence

from openai import AsyncAzureOpenAI

from aisos.config import AppConfig

EMBED_DIM = 1536


class EmbeddingsClient:
    """Async batch-capable embeddings via AsyncAzureOpenAI."""

    def __init__(self, config: AppConfig, client: AsyncAzureOpenAI | None = None) -> None:
        self._config = config
        self._client = client or AsyncAzureOpenAI(
            azure_endpoint=config.settings.azure_openai_endpoint,
            api_key=config.settings.azure_openai_api_key,
            api_version=config.settings.azure_openai_api_version,
        )
        self._deployment = config.settings.azure_openai_deployment_embed

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding per text (preserves order)."""
        if not texts:
            return []
        resp = await self._client.embeddings.create(
            model=self._deployment, input=list(texts)
        )
        return [d.embedding for d in resp.data]


__all__ = ["EMBED_DIM", "EmbeddingsClient"]
