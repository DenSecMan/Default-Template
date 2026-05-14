"""SavePlaybookTool: persist a named investigation playbook to ProceduralMemory."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from aisos.memory.procedural import ProceduralMemory
from aisos.tools.base import BaseTool


class SavePlaybookInput(BaseModel):
    name: str = Field(..., description="Unique slug for the playbook, e.g. 'triage-ip'.")
    description: str = Field(..., description="One-line summary of what the playbook does.")
    steps: list[dict[str, Any]] = Field(
        ...,
        description=(
            "List of StepNode-compatible dicts. Each must have: id (string), "
            "description (string), tool (string|null), args (object), "
            "depends_on (list of step ids). Use {{param}} placeholders for "
            "values that vary per run, e.g. args: {indicator: '{{ip}}'}."
        ),
    )


class SavePlaybookTool(BaseTool):
    name = "save_playbook"
    description = (
        "Save a named investigation playbook to procedural memory so it can be "
        "replayed later with run_playbook. Provide a slug name, a description, "
        "and the full list of steps (same format as a plan DAG). "
        "Use {{param}} placeholders for values that vary per invocation."
    )
    input_schema = SavePlaybookInput
    risk_level = "low"
    required_scope = "read"

    def __init__(self, procedural: ProceduralMemory | None = None) -> None:
        self._procedural = procedural

    async def run(self, input: SavePlaybookInput) -> dict[str, Any]:  # type: ignore[override]
        if self._procedural is None:
            return {"text": "Procedural memory is not connected — playbook not saved."}
        self._procedural.save_recipe(
            input.name,
            {"description": input.description, "steps": input.steps},
        )
        return {
            "text": (
                f"Playbook '{input.name}' saved with {len(input.steps)} step(s). "
                f"Run it with: run_playbook(name='{input.name}', params={{...}})"
            )
        }


__all__ = ["SavePlaybookInput", "SavePlaybookTool"]
