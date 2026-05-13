"""Test-only high-risk tool: echoes its input but is gated by HITL.

Kept under tools/ so the auto-discovery scanner finds it. Marked risk_level=high
so HITL approval is mandatory.
"""

from __future__ import annotations

from pydantic import BaseModel

from aisos.tools.base import BaseTool


class DangerousInput(BaseModel):
    payload: str


class DangerousDemoTool(BaseTool):
    name = "dangerous_demo"
    description = "High-risk demo tool (HITL-gated)."
    input_schema = DangerousInput
    risk_level = "high"
    required_scope = "write"

    async def run(self, input: DangerousInput) -> dict[str, str]:  # type: ignore[override]
        return {"text": f"executed: {input.payload}"}


__all__ = ["DangerousDemoTool", "DangerousInput"]
