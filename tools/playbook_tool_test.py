"""Tests for save_playbook and run_playbook tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from aisos.memory.db import get_connection
from aisos.memory.procedural import ProceduralMemory
from tools.run_playbook_tool import RunPlaybookInput, RunPlaybookTool, _substitute
from tools.save_playbook_tool import SavePlaybookInput, SavePlaybookTool

_STEPS = [
    {"id": "s1", "description": "check", "tool": "virustotal_lookup",
     "args": {"indicator": "{{ip}}", "indicator_type": "ip"}, "depends_on": []},
]


# ---------------------------------------------------------------------------
# _substitute helper
# ---------------------------------------------------------------------------

def test_substitute_replaces_in_strings() -> None:
    assert _substitute("hello {{name}}", {"name": "world"}) == "hello world"


def test_substitute_recurses_into_dicts_and_lists() -> None:
    obj = {"a": "{{x}}", "b": ["{{x}}", {"c": "{{x}}"}]}
    result = _substitute(obj, {"x": "Z"})
    assert result == {"a": "Z", "b": ["Z", {"c": "Z"}]}


def test_substitute_leaves_unmatched_placeholders_intact() -> None:
    assert _substitute("{{missing}}", {}) == "{{missing}}"


# ---------------------------------------------------------------------------
# SavePlaybookTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_playbook_persists_recipe(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    pm = ProceduralMemory(conn)
    tool = SavePlaybookTool(procedural=pm)

    result = await tool.run(SavePlaybookInput(
        name="triage-ip", description="Triage an IP", steps=_STEPS,
    ))

    assert "triage-ip" in result["text"]
    recipe = pm.load_recipe("triage-ip")
    assert recipe is not None
    assert recipe.plan["steps"] == _STEPS
    conn.close()


@pytest.mark.asyncio
async def test_save_playbook_without_memory_returns_error() -> None:
    tool = SavePlaybookTool(procedural=None)
    result = await tool.run(SavePlaybookInput(name="x", description="y", steps=[]))
    assert "not connected" in result["text"]


# ---------------------------------------------------------------------------
# RunPlaybookTool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_playbook_not_found_returns_hint(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    pm = ProceduralMemory(conn)
    pm.save_recipe("existing", {"steps": []})
    tool = RunPlaybookTool(procedural=pm)

    result = await tool.run(RunPlaybookInput(name="missing"))
    assert "not found" in result["text"]
    assert "existing" in result["text"]
    conn.close()


@pytest.mark.asyncio
async def test_run_playbook_returns_inject_steps(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    pm = ProceduralMemory(conn)
    pm.save_recipe("triage-ip", {"description": "d", "steps": _STEPS})
    tool = RunPlaybookTool(procedural=pm)

    result = await tool.run(RunPlaybookInput(name="triage-ip", params={"ip": "1.2.3.4"}))

    assert "inject_steps" in result
    assert result["inject_steps"][0]["args"]["indicator"] == "1.2.3.4"
    assert "triage-ip" in result["text"]
    conn.close()


@pytest.mark.asyncio
async def test_run_playbook_without_params_keeps_placeholders(tmp_path: Path) -> None:
    conn = get_connection(tmp_path / "m.db")
    pm = ProceduralMemory(conn)
    pm.save_recipe("pb", {"steps": _STEPS})
    tool = RunPlaybookTool(procedural=pm)

    result = await tool.run(RunPlaybookInput(name="pb"))
    assert result["inject_steps"][0]["args"]["indicator"] == "{{ip}}"
    conn.close()


@pytest.mark.asyncio
async def test_run_playbook_without_memory_returns_error() -> None:
    tool = RunPlaybookTool(procedural=None)
    result = await tool.run(RunPlaybookInput(name="x"))
    assert "not connected" in result["text"]
