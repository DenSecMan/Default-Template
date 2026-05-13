"""Planner: prompts the LLM for a JSON DAG, parses via Pydantic."""

from __future__ import annotations

import json
import re
from typing import Sequence

from pydantic import ValidationError

from aisos.intelligence.base import ChatMessage
from aisos.intelligence.router import Router
from aisos.orchestration.state import AgentState, StepNode

_PLAN_SYSTEM = (
    "You are the AISOS planner. Output ONLY a JSON object with a 'plan' key whose "
    "value is a list of step objects. Each step must have: id (string), description "
    "(string), tool (string|null), args (object), depends_on (list of step ids). "
    "No prose, no markdown fences."
)

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def _extract_json(text: str) -> str:
    text = text.strip()
    text = _FENCE_RE.sub("", text).strip()
    return text


def parse_plan(raw: str) -> list[StepNode]:
    """Parse an LLM plan response into StepNode list. Raises ValueError on bad input."""
    cleaned = _extract_json(raw)
    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"Planner output not JSON: {e}") from e
    if not isinstance(obj, dict) or "plan" not in obj:
        raise ValueError("Planner output must be an object with a 'plan' key.")
    try:
        return [StepNode.model_validate(s) for s in obj["plan"]]
    except ValidationError as e:
        raise ValueError(f"Planner step did not validate: {e}") from e


class Planner:
    """LangGraph-style node: prompt -> plan."""

    def __init__(self, router: Router, capability: str = "plan") -> None:
        self._router = router
        self._capability = capability

    async def __call__(self, state: AgentState) -> AgentState:
        return await self.plan(state)

    async def plan(self, state: AgentState) -> AgentState:
        route = self._router.route(self._capability)
        messages: Sequence[ChatMessage] = [
            {"role": "system", "content": _PLAN_SYSTEM},
            {"role": "user", "content": state.prompt},
        ]
        raw = await route.provider.chat(messages, model=route.model)
        state.plan = parse_plan(raw)
        return state


__all__ = ["Planner", "parse_plan"]
