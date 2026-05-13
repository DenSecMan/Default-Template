"""Tests for orchestration.state."""

from __future__ import annotations

from aisos.orchestration.state import AgentState, StepNode


def test_default_agent_state() -> None:
    s = AgentState(prompt="hi")
    assert s.plan == []
    assert s.current_step == 0
    assert s.history == []
    assert s.results == {}
    assert s.error is None


def test_step_node_validation() -> None:
    n = StepNode(id="a", description="do thing")
    assert n.status == "pending"
    assert n.depends_on == []
