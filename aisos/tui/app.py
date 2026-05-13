"""Wired AISOS Textual app: input -> orchestrator -> output + trace + HITL modal."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import Footer, Header, Input

from aisos.config import AppConfig, load_config
from aisos.intelligence.azure_openai import AzureOpenAIProvider
from aisos.intelligence.router import Router
from aisos.observability.audit_log import AuditLog
from aisos.observability.cost_tracker import CostTracker
from aisos.observability.trace import TRACE_TOPIC
from aisos.orchestration.event_bus import Event, EventBus
from aisos.orchestration.orchestrator import Orchestrator
from aisos.orchestration.planner import Planner
from aisos.orchestration.registry import AgentRegistry, AgentSpec
from aisos.security.hitl import REQUEST_TOPIC, RESPONSE_TOPIC
from aisos.security.sanitizer import redact_output
from aisos.tools.registry import ToolRegistry
from aisos.tui.commands import CommandContext, dispatch, is_command
from aisos.tui.widgets import HITLModal, StreamingOutput, TracePanel


class AISOSApp(App[int]):
    """Top-level AISOS Textual app."""

    TITLE = "AISOS"
    SUB_TITLE = "Agentic Intelligence Shell OS"
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    Input { dock: bottom; }
    """

    def __init__(
        self,
        config: AppConfig | None = None,
        bus: EventBus | None = None,
        tools: ToolRegistry | None = None,
        agents: AgentRegistry | None = None,
        orchestrator: Orchestrator | None = None,
    ) -> None:
        super().__init__()
        self._config = config or load_config()
        self._bus = bus or EventBus()
        self._tools = tools or self._build_tools()
        self._agents = agents or self._build_agents()
        self._cost = CostTracker(self._config)
        self._audit = AuditLog("aisos.audit.log")
        self._orchestrator = orchestrator or self._build_orchestrator()
        self._trace: TracePanel | None = None
        self._output: StreamingOutput | None = None
        self._hitl_task: asyncio.Task[None] | None = None

    @staticmethod
    def _build_tools() -> ToolRegistry:
        reg = ToolRegistry()
        reg.discover("tools")
        return reg

    @staticmethod
    def _build_agents() -> AgentRegistry:
        reg = AgentRegistry()
        reg.register(AgentSpec(name="planner", description="DAG planner", allowed_tool_scopes=["read", "write", "compute"]))
        reg.register(AgentSpec(name="default", description="Default agent", allowed_tool_scopes=["read"]))
        return reg

    def _build_orchestrator(self) -> Orchestrator:
        provider = AzureOpenAIProvider(self._config)
        router = Router(self._config, {"azure_openai": provider})
        planner = Planner(router)
        return Orchestrator(
            self._config, self._bus, planner, self._tools,
            agent_name="planner", audit=self._audit, cost_tracker=self._cost,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main"):
            self._trace = TracePanel(id="trace")
            yield self._trace
            self._output = StreamingOutput(id="output")
            yield self._output
        yield Input(placeholder="Type a prompt or /help…", id="cmd")
        yield Footer()

    def on_mount(self) -> None:
        self._hitl_task = asyncio.create_task(self._listen_hitl())
        asyncio.create_task(self._listen_trace())

    async def _listen_hitl(self) -> None:
        async for ev in self._bus.subscribe(REQUEST_TOPIC):
            req_id = ev.payload["request_id"]
            tool_name = ev.payload["tool_name"]
            summary = str(ev.payload.get("summary", {}))
            approved = await self.push_screen_wait(HITLModal(req_id, tool_name, summary))
            await self._bus.publish(
                Event(RESPONSE_TOPIC, {"request_id": req_id, "approved": bool(approved)})
            )

    async def _listen_trace(self) -> None:
        async for ev in self._bus.subscribe(TRACE_TOPIC):
            if self._trace is None:
                continue
            self._trace.update_node(ev.payload["node_id"], ev.payload["status"])

    def write_output(self, text: str) -> None:
        if self._output is not None:
            self._output.append_block(redact_output(text))

    def request_quit(self) -> None:
        self.exit(0)

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        text = message.value.strip()
        message.input.value = ""
        if not text:
            return
        if is_command(text):
            ctx = CommandContext(app=self, tools=self._tools, agents=self._agents, cost=self._cost)
            dispatch(ctx, text)
            return
        self.write_output(f"> {text}")
        try:
            result = await self._orchestrator.run(text)
        except Exception as exc:  # surfaced to user
            self.write_output(f"[error] {exc}")
            return
        if result.output_text:
            self.write_output(result.output_text)


__all__ = ["AISOSApp"]
