"""Tool ABC consumed by the orchestration loop and the registry scanner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, ClassVar, Literal

from pydantic import BaseModel

RiskLevel = Literal["low", "medium", "high"]


class BaseTool(ABC):
    """All tools (built-in or under tools/) inherit this contract."""

    name: ClassVar[str]
    description: ClassVar[str]
    input_schema: ClassVar[type[BaseModel]]
    risk_level: ClassVar[RiskLevel] = "low"
    required_scope: ClassVar[str] = "read"

    @abstractmethod
    async def run(self, input: BaseModel) -> Any:
        """Execute the tool and return a JSON-serialisable result."""

    def validate(self, raw: dict[str, Any]) -> BaseModel:
        return self.input_schema.model_validate(raw)


__all__ = ["BaseTool", "RiskLevel"]
