"""Wired AISOS Textual app: two-column chat + sidebar (plan/session/tools)."""

from __future__ import annotations

import asyncio

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Input

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
from aisos.tui.widgets import (
    ChatLog,
    HITLModal,
    PlanPanel,
    SessionPanel,
    ToolPanel,
)


class AISOSApp(App[int]):
    """Top-level AISOS Textual app."""

    TITLE = "AISOS"
    SUB_TITLE = "Agentic Intelligence Shell OS"
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear chat"),
    ]

    CSS = """
    Screen { layout: vertical; }
    #body { height: 1fr; }
    #chat-pane { width: 2fr; }
    #sidebar {
        width: 36;
        min-width: 28;
        padding: 1 1 0 0;
    }
    #cmd { dock: bottom; margin: 0 1 0 1; }
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
        self._chat: ChatLog | None = None
        self._plan: PlanPanel | None = None
        self._session: SessionPanel | None = None
        self._tools_panel: ToolPanel | None = None
        self._steps_total = 0

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
        planner = Planner(router, tools=self._tools, cost_tracker=self._cost)
        return Orchestrator(
            self._config, self._bus, planner, self._tools,
            agent_name="planner", audit=self._audit, cost_tracker=self._cost,
        )

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            self._chat = ChatLog(id="chat-pane")
            yield self._chat
            with Vertical(id="sidebar"):
                self._plan = PlanPanel(id="plan")
                yield self._plan
                self._session = SessionPanel(id="session")
                yield self._session
                self._tools_panel = ToolPanel(id="tools")
                yield self._tools_panel
        yield Input(placeholder="Type a prompt or /help…  (^q quit, ^l clear)", id="cmd")

    def on_mount(self) -> None:
        # Populate static panels.
        if self._tools_panel is not None:
            self._tools_panel.set_tools(
                (t.name, t.risk_level) for t in self._tools.all()
            )
        self._refresh_session_panel()
        # Background listeners.
        asyncio.create_task(self._listen_hitl())
        asyncio.create_task(self._listen_trace())
        # Welcome message.
        asyncio.create_task(self._post(
            "system",
            "Welcome to **AISOS**. Type a prompt, or `/help` for commands.",
            render_markdown=True,
        ))

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
            if self._plan is None:
                continue
            self._plan.update_node(ev.payload["node_id"], ev.payload["status"])
            if ev.payload["status"] in ("complete", "failed"):
                self._steps_total += 1
                self._refresh_session_panel()

    async def _post(self, role: str, body: str, *, render_markdown: bool = True) -> None:
        if self._chat is None:
            return
        await self._chat.post_message_block(role, redact_output(body), render_markdown=render_markdown)

    def _refresh_session_panel(self) -> None:
        if self._session is None:
            return
        s = self._cost.summary()
        self._session.set_summary(
            cost_usd=s.total.usd,
            in_tokens=s.total.in_tokens,
            out_tokens=s.total.out_tokens,
            steps=self._steps_total,
            deployment=self._config.settings.azure_openai_deployment_chat,
        )

    def write_output(self, text: str) -> None:
        """Used by slash-command dispatcher."""
        asyncio.create_task(self._post("system", text, render_markdown=False))

    def request_quit(self) -> None:
        self.exit(0)

    def action_clear(self) -> None:
        if self._chat is None:
            return
        for child in list(self._chat.children):
            child.remove()
        if self._plan is not None:
            self._plan.reset()
        self._steps_total = 0
        self._refresh_session_panel()

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        text = message.value.strip()
        message.input.value = ""
        if not text:
            return
        if is_command(text):
            ctx = CommandContext(app=self, tools=self._tools, agents=self._agents, cost=self._cost)
            dispatch(ctx, text)
            return
        await self._post("user", text, render_markdown=False)
        if self._plan is not None:
            self._plan.reset()
        try:
            result = await self._orchestrator.run(text)
        except Exception as exc:
            await self._post("error", f"{type(exc).__name__}: {exc}", render_markdown=False)
            return
        # Reflect the planned nodes immediately even if no trace events fired
        # for them yet (they will be marked complete via _listen_trace).
        if self._plan is not None and result.state.plan:
            for node in result.state.plan:
                self._plan.update_node(node.id, node.status)
        if result.output_text:
            await self._post("assistant", result.output_text, render_markdown=True)
        self._refresh_session_panel()


__all__ = ["AISOSApp"]
