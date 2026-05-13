"""End-to-end orchestrator wiring sanitizer -> planner -> tools (HITL+RBAC) -> trace."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from aisos.config import AppConfig
from aisos.observability.audit_log import AuditEntry, AuditLog
from aisos.observability.cost_tracker import CostTracker
from aisos.observability.trace import Tracer
from aisos.orchestration.event_bus import EventBus
from aisos.orchestration.loop_guard import check as guard_check
from aisos.orchestration.planner import Planner
from aisos.orchestration.state import AgentState, StepNode
from aisos.security.hitl import HITLGate
from aisos.security.rbac import check as rbac_check
from aisos.security.sanitizer import redact_output, screen_input
from aisos.tools.registry import ToolRegistry


@dataclass
class RunResult:
    state: AgentState
    output_text: str


class Orchestrator:
    """Glues the framework together for one prompt."""

    def __init__(
        self,
        config: AppConfig,
        bus: EventBus,
        planner: Planner,
        tools: ToolRegistry,
        agent_name: str = "default",
        audit: AuditLog | None = None,
        cost_tracker: CostTracker | None = None,
        hitl_timeout_s: float | None = None,
    ) -> None:
        self._config = config
        self._bus = bus
        self._planner = planner
        self._tools = tools
        self._agent_name = agent_name
        self._tracer = Tracer(bus)
        self._hitl = HITLGate(bus, timeout_s=hitl_timeout_s)
        self._audit = audit
        self._cost = cost_tracker

    async def run(self, prompt: str) -> RunResult:
        screened = screen_input(prompt)
        state = AgentState(prompt=screened.text)
        await self._planner(state)

        output_chunks: list[str] = []
        for node in state.plan:
            state.current_step += 1
            guard_check(state, self._config.toml.max_steps)
            await self._tracer.emit(node.id, "running", agent=self._agent_name)
            try:
                result = await self._exec_node(node)
            except Exception as exc:
                node.status = "failed"
                state.error = str(exc)
                await self._tracer.emit(
                    node.id, "failed", agent=self._agent_name, detail={"error": str(exc)}
                )
                self._record_audit(node, error=str(exc))
                raise
            else:
                node.status = "complete"
                state.results[node.id] = result
                await self._tracer.emit(
                    node.id, "complete", agent=self._agent_name, detail={"result": result}
                )
                self._record_audit(node, output=result)
                if isinstance(result, dict) and "text" in result:
                    output_chunks.append(str(result["text"]))
        # If no text came from noop steps, summarize tool results via LLM.
        if not output_chunks:
            tool_results = {
                nid: res for nid, res in state.results.items()
                if isinstance(res, dict) and "text" not in res
            }
            if tool_results:
                summary = await self._planner.summarize(state.prompt, tool_results)
                output_chunks.append(summary)

        text = redact_output("\n".join(output_chunks))
        return RunResult(state=state, output_text=text)

    async def _exec_node(self, node: StepNode) -> Any:
        if node.tool is None:
            return {"text": node.description}
        try:
            tool = self._tools.get(node.tool)
        except KeyError:
            # Planner referenced a tool that isn't registered. Degrade to the
            # description so the user still gets something useful.
            return {"text": f"(planner referenced unknown tool '{node.tool}'; "
                            f"falling back to description)\n{node.description}"}
        rbac_check(self._config, self._agent_name, tool.required_scope)
        await self._hitl.gate(tool, node.args)
        validated = tool.validate(node.args)
        return await tool.run(validated)

    def _record_audit(
        self,
        node: StepNode,
        output: Any | None = None,
        error: str | None = None,
    ) -> None:
        if self._audit is None:
            return
        self._audit.append(
            AuditEntry(
                agent=self._agent_name,
                action=node.tool or "noop",
                input_summary=str(node.args)[:200],
                output_summary=("error: " + error) if error else str(output)[:200],
            )
        )


async def run_prompt(orch: Orchestrator, prompt: str) -> RunResult:
    return await asyncio.shield(orch.run(prompt))


__all__ = ["Orchestrator", "RunResult", "run_prompt"]
