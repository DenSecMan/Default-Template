"""RunPlaybookTool: load a saved playbook and inject its steps into the live plan."""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field

from aisos.memory.procedural import ProceduralMemory
from aisos.tools.base import BaseTool


class RunPlaybookInput(BaseModel):
    name: str = Field(..., description="Slug of the playbook to run, e.g. 'triage-ip'.")
    params: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Key/value substitutions applied to every {{placeholder}} in the "
            "stored step args. E.g. {\"ip\": \"203.0.113.42\"} replaces every "
            "occurrence of '{{ip}}' in the stored steps."
        ),
    )


def _substitute(obj: Any, params: dict[str, str]) -> Any:
    """Recursively replace {{key}} placeholders in any JSON-serialisable structure."""
    if isinstance(obj, str):
        for key, val in params.items():
            obj = obj.replace(f"{{{{{key}}}}}", val)
        return obj
    if isinstance(obj, dict):
        return {k: _substitute(v, params) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(item, params) for item in obj]
    return obj


class RunPlaybookTool(BaseTool):
    name = "run_playbook"
    description = (
        "Load a saved playbook by name and execute its steps. "
        "Pass a params dict to substitute {{placeholder}} values in the stored steps. "
        "The playbook steps are injected directly into the running plan — "
        "no extra LLM call is made."
    )
    input_schema = RunPlaybookInput
    risk_level = "low"
    required_scope = "read"

    def __init__(self, procedural: ProceduralMemory | None = None) -> None:
        self._procedural = procedural

    async def run(self, input: RunPlaybookInput) -> dict[str, Any]:  # type: ignore[override]
        if self._procedural is None:
            return {"text": "Procedural memory is not connected — cannot load playbook."}

        recipe = self._procedural.load_recipe(input.name)
        if recipe is None:
            names = [r.name for r in self._procedural.list_recipes()]
            hint = f" Available: {', '.join(names)}" if names else " No playbooks saved yet."
            return {"text": f"Playbook '{input.name}' not found.{hint}"}

        raw_steps: list[dict[str, Any]] = recipe.plan.get("steps", [])
        steps = _substitute(raw_steps, input.params)

        return {
            "inject_steps": steps,
            "text": (
                f"Running playbook '{input.name}' "
                f"({len(steps)} step(s), params={json.dumps(input.params) or '{}'})…"
            ),
        }


__all__ = ["RunPlaybookInput", "RunPlaybookTool", "_substitute"]
