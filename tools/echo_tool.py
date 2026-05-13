"""EchoTool: returns input verbatim."""

from __future__ import annotations

from pydantic import BaseModel

from aisos.tools.base import BaseTool


class EchoInput(BaseModel):
    text: str


class EchoTool(BaseTool):
    name = "echo"
    description = "Return the provided text verbatim."
    input_schema = EchoInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: EchoInput) -> dict[str, str]:  # type: ignore[override]
        return {"text": input.text}


__all__ = ["EchoInput", "EchoTool"]
