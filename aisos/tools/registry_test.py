"""Tests for tools.registry discovery."""

from __future__ import annotations

from pathlib import Path

import pytest

from aisos.tools.registry import ToolRegistry


def test_discover_finds_builtin_tools() -> None:
    reg = ToolRegistry()
    found = reg.discover("tools")
    names = {t.name for t in found}
    assert "echo" in names
    assert "web_search" in names


def test_discover_path_picks_up_dynamic_tool(tmp_path: Path) -> None:
    (tmp_path / "extra_tool.py").write_text(
        """
from pydantic import BaseModel
from aisos.tools.base import BaseTool

class _In(BaseModel):
    x: int

class ExtraTool(BaseTool):
    name = "extra"
    description = "double the input"
    input_schema = _In
    risk_level = "low"
    required_scope = "read"

    async def run(self, input):
        return {"x2": input.x * 2}
""".strip(),
        encoding="utf-8",
    )
    reg = ToolRegistry()
    found = reg.discover_path(tmp_path)
    assert {t.name for t in found} == {"extra"}


@pytest.mark.asyncio
async def test_discover_lookup_and_run() -> None:
    reg = ToolRegistry()
    reg.discover("tools")
    echo = reg.get("echo")
    payload = echo.validate({"text": "hi"})
    out = await echo.run(payload)
    assert out == {"text": "hi"}


def test_get_missing_raises() -> None:
    with pytest.raises(KeyError):
        ToolRegistry().get("nope")
