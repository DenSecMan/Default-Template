"""Agent Registry: declarative agent specs."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentSpec:
    name: str
    description: str
    allowed_tool_scopes: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


class AgentRegistry:
    """In-memory registry of agent specs."""

    def __init__(self) -> None:
        self._agents: dict[str, AgentSpec] = {}

    def register(self, spec: AgentSpec) -> None:
        if spec.name in self._agents:
            raise ValueError(f"Agent '{spec.name}' already registered.")
        self._agents[spec.name] = spec

    def get(self, name: str) -> AgentSpec:
        try:
            return self._agents[name]
        except KeyError as e:
            raise KeyError(f"Agent '{name}' not registered.") from e

    def all(self) -> list[AgentSpec]:
        return list(self._agents.values())

    def has(self, name: str) -> bool:
        return name in self._agents


__all__ = ["AgentRegistry", "AgentSpec"]
