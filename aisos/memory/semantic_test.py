"""Tests for memory.semantic with a deterministic stub embedder."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Sequence

import pytest

from aisos.memory.db import get_connection
from aisos.memory.semantic import SemanticMemory


class _StubEmbedder:
    """Deterministic 1536-d embedder: hashes the text into a sparse signal."""

    DIM = 1536

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.DIM
            for i, ch in enumerate(text.encode("utf-8")):
                vec[(ch * 13 + i) % self.DIM] += 1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            vec = [v / norm for v in vec]
            out.append(vec)
        return out


@pytest.mark.asyncio
async def test_search_returns_closest_first(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "v.db")
    mem = SemanticMemory(conn, _StubEmbedder())
    await mem.add("the quick brown fox", {"id": "fox"})
    await mem.add("totally unrelated text about cars", {"id": "car"})
    await mem.add("the quick brown dog", {"id": "dog"})

    hits = await mem.search("the quick brown fox", k=3)
    assert len(hits) == 3
    assert hits[0].metadata["id"] == "fox"
    distances = [h.distance for h in hits]
    assert distances == sorted(distances)
    conn.close()
