"""LangGraph-compatible Pydantic state model."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

StepStatus = Literal["pending", "running", "complete", "failed"]


class StepNode(BaseModel):
    """One node in the planner's DAG."""

    id: str
    description: str
    tool: str | None = None
    args: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    status: StepStatus = "pending"


class AgentState(BaseModel):
    """Mutable run state passed through the orchestration graph."""

    prompt: str
    plan: list[StepNode] = Field(default_factory=list)
    current_step: int = 0
    history: list[dict[str, Any]] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


__all__ = ["AgentState", "StepNode", "StepStatus"]
