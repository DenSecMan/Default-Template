"""Procedural memory: workflow recipe CRUD."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class Recipe:
    name: str
    plan: dict[str, Any]
    created_at: float
    updated_at: float


class ProceduralMemory:
    """Named workflow plans stored as JSON."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def save_recipe(self, name: str, plan: dict[str, Any]) -> Recipe:
        now = time.time()
        plan_json = json.dumps(plan, ensure_ascii=False)
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO recipes(name, plan_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    plan_json = excluded.plan_json,
                    updated_at = excluded.updated_at;
                """,
                (name, plan_json, now, now),
            )
        return self.load_recipe(name)  # type: ignore[return-value]

    def load_recipe(self, name: str) -> Recipe | None:
        cur = self._conn.execute(
            "SELECT name, plan_json, created_at, updated_at FROM recipes WHERE name=?;",
            (name,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        return Recipe(
            name=row["name"],
            plan=json.loads(row["plan_json"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def list_recipes(self) -> list[Recipe]:
        cur = self._conn.execute(
            "SELECT name, plan_json, created_at, updated_at FROM recipes ORDER BY name;"
        )
        return [
            Recipe(
                name=r["name"],
                plan=json.loads(r["plan_json"]),
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
            for r in cur.fetchall()
        ]

    def delete_recipe(self, name: str) -> bool:
        with self._conn:
            cur = self._conn.execute("DELETE FROM recipes WHERE name=?;", (name,))
        return cur.rowcount > 0


__all__ = ["ProceduralMemory", "Recipe"]
