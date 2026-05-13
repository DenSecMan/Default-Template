"""Loop guard: aborts orchestration when current_step exceeds max_steps."""

from __future__ import annotations

from aisos.orchestration.state import AgentState


class LoopGuardError(RuntimeError):
    """Raised when the orchestration loop exceeds its step budget."""


def check(state: AgentState, max_steps: int) -> None:
    """Raise LoopGuardError if we've stepped past the budget."""
    if state.current_step > max_steps:
        raise LoopGuardError(
            f"Step counter {state.current_step} exceeded max_steps={max_steps}"
        )


__all__ = ["LoopGuardError", "check"]
