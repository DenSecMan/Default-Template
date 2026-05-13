"""Long-term semantic memory: sqlite-vec similarity search."""

from __future__ import annotations

import json
import sqlite3
import struct
import time
from dataclasses import dataclass
from typing import Any, Protocol, Sequence


class _Embedder(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


def _to_blob(vec: Sequence[float]) -> bytes:
    return struct.pack(f"{len(vec)}f", *vec)


@dataclass
class SemanticHit:
    rowid: int
    text: str
    metadata: dict[str, Any]
    distance: float


class SemanticMemory:
    """Insert + cosine-similarity search backed by sqlite-vec vec0."""

    def __init__(self, conn: sqlite3.Connection, embedder: _Embedder) -> None:
        self._conn = conn
        self._embedder = embedder

    async def add(self, text: str, metadata: dict[str, Any] | None = None) -> int:
        vec = (await self._embedder.embed([text]))[0]
        return self._insert(text, vec, metadata or {})

    async def add_batch(
        self, items: Sequence[tuple[str, dict[str, Any]]]
    ) -> list[int]:
        if not items:
            return []
        texts = [t for t, _ in items]
        vecs = await self._embedder.embed(texts)
        ids: list[int] = []
        for (text, meta), vec in zip(items, vecs, strict=True):
            ids.append(self._insert(text, vec, meta))
        return ids

    def _insert(self, text: str, vec: Sequence[float], metadata: dict[str, Any]) -> int:
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO vec_embeddings(embedding) VALUES (?);", (_to_blob(vec),)
            )
            rowid = int(cur.lastrowid or 0)
            self._conn.execute(
                "INSERT INTO vec_embeddings_meta(rowid, text, metadata, created_at) "
                "VALUES (?, ?, ?, ?);",
                (rowid, text, json.dumps(metadata, ensure_ascii=False), time.time()),
            )
        return rowid

    async def search(self, query: str, k: int = 5) -> list[SemanticHit]:
        vec = (await self._embedder.embed([query]))[0]
        return self._search_vec(vec, k)

    def _search_vec(self, vec: Sequence[float], k: int) -> list[SemanticHit]:
        cur = self._conn.execute(
            """
            SELECT v.rowid AS rowid, v.distance AS distance,
                   m.text AS text, m.metadata AS metadata
            FROM vec_embeddings v
            JOIN vec_embeddings_meta m ON m.rowid = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance;
            """,
            (_to_blob(vec), k),
        )
        hits: list[SemanticHit] = []
        for row in cur.fetchall():
            hits.append(
                SemanticHit(
                    rowid=row["rowid"],
                    text=row["text"],
                    metadata=json.loads(row["metadata"] or "{}"),
                    distance=float(row["distance"]),
                )
            )
        return hits


__all__ = ["SemanticHit", "SemanticMemory"]
