"""Planner: prompts the LLM for a JSON DAG, parses via Pydantic."""

from __future__ import annotations

import json
import re
from typing import Sequence

from pydantic import ValidationError

from aisos.intelligence.base import ChatMessage
from aisos.intelligence.router import Router
from aisos.intelligence.token_controller import count_messages, count_tokens
from aisos.observability.cost_tracker import CostTracker
from aisos.orchestration.state import AgentState, StepNode
from aisos.tools.registry import ToolRegistry

_PLAN_SYSTEM_TEMPLATE = (
    "You are the AISOS planner. Decompose the user's request into a JSON DAG.\n\n"
    "Output ONLY a JSON object with a 'plan' key whose value is a list of step objects. "
    "Each step must have: id (string), description (string), tool (string|null), "
    "args (object), depends_on (list of step ids). "
    "No prose, no markdown fences.\n\n"
    "Tool selection rules:\n"
    "- ONLY use tools from the catalog below; never invent tool names.\n"
    "- For questions you can answer directly (greetings, status, simple Q&A), set "
    "tool=null and put the answer in 'description'.\n"
    "- 'args' must match the named tool's input schema.\n\n"
    "Tool catalog:\n{catalog}"
)


def _format_catalog(tools: ToolRegistry | None) -> str:
    if tools is None or not tools.all():
        return "(no tools registered — use tool=null and answer in description)"
    lines = []
    for t in tools.all():
        schema = t.input_schema.model_json_schema()
        props = schema.get("properties", {})
        arg_summary = ", ".join(f"{k}: {v.get('type', '?')}" for k, v in props.items()) or "(no args)"
        lines.append(f"- {t.name} (risk={t.risk_level}): {t.description} | args: {arg_summary}")
    return "\n".join(lines)

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

    def __init__(
        self,
        router: Router,
        capability: str = "plan",
        tools: ToolRegistry | None = None,
        cost_tracker: CostTracker | None = None,
        agent_name: str = "planner",
    ) -> None:
        self._router = router
        self._capability = capability
        self._tools = tools
        self._cost = cost_tracker
        self._agent_name = agent_name

    async def __call__(self, state: AgentState) -> AgentState:
        return await self.plan(state)

    async def plan(self, state: AgentState) -> AgentState:
        route = self._router.route(self._capability)
        system = _PLAN_SYSTEM_TEMPLATE.format(catalog=_format_catalog(self._tools))
        messages: Sequence[ChatMessage] = [
            {"role": "system", "content": system},
            {"role": "user", "content": state.prompt},
        ]
        raw = await route.provider.chat(messages, model=route.model)
        if self._cost is not None:
            in_tokens = count_messages(messages, route.model or "gpt-4o")
            out_tokens = count_tokens(raw, route.model or "gpt-4o")
            self._cost.record(
                route.model or "gpt-4o", in_tokens, out_tokens, agent=self._agent_name
            )
        state.plan = parse_plan(raw)
        return state


__all__ = ["Planner", "parse_plan"]
