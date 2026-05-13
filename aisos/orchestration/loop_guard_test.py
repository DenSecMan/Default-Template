"""Tests for orchestration.loop_guard."""

from __future__ import annotations

import pytest

from aisos.orchestration.loop_guard import LoopGuardError, check
from aisos.orchestration.state import AgentState


def test_within_budget_passes() -> None:
    s = AgentState(prompt="x", current_step=5)
    check(s, max_steps=10)  # no raise


def test_exceeded_budget_raises() -> None:
    s = AgentState(prompt="x", current_step=11)
    with pytest.raises(LoopGuardError):
        check(s, max_steps=10)
