"""Tests for orchestration.registry."""

from __future__ import annotations

import pytest

from aisos.orchestration.registry import AgentRegistry, AgentSpec


def test_register_and_lookup() -> None:
    r = AgentRegistry()
    spec = AgentSpec(name="planner", description="d", allowed_tool_scopes=["read"])
    r.register(spec)
    assert r.has("planner")
    assert r.get("planner") is spec


def test_duplicate_register_raises() -> None:
    r = AgentRegistry()
    r.register(AgentSpec(name="a", description=""))
    with pytest.raises(ValueError):
        r.register(AgentSpec(name="a", description=""))


def test_get_missing_raises() -> None:
    with pytest.raises(KeyError):
        AgentRegistry().get("nope")
