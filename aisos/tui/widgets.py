"""TUI widgets: chat messages, sidebar panels, HITL modal."""

from __future__ import annotations

from typing import Iterable, Sequence

from rich.markdown import Markdown
from rich.markup import escape as markup_escape
from rich.text import Text
from textual import events, on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, OptionList, Static
from textual.widgets.option_list import Option

_STATUS_GLYPH = {
    "pending": "·",
    "running": "▶",
    "complete": "✓",
    "failed": "✗",
}


class ChatMessage(Static):
    """One styled message bubble with a role header."""

    DEFAULT_CSS = """
    ChatMessage {
        margin: 1 2 0 2;
        height: auto;
        padding: 0;
    }
    ChatMessage > .role {
        height: 1;
        padding: 0 1;
        text-style: bold;
    }
    ChatMessage > .role.-user      { color: $accent; }
    ChatMessage > .role.-assistant { color: $success; }
    ChatMessage > .role.-system    { color: $warning; }
    ChatMessage > .role.-error     { color: $error; }
    ChatMessage > .body {
        height: auto;
        padding: 0 1;
        background: $boost;
        border: tall $surface;
    }
    ChatMessage > .body.-user      { border-left: thick $accent; }
    ChatMessage > .body.-assistant { border-left: thick $success; }
    ChatMessage > .body.-system    { border-left: thick $warning; }
    ChatMessage > .body.-error     { border-left: thick $error; }
    """

    def __init__(self, role: str, body: str | Markdown | Text, *, render_markdown: bool = True) -> None:
        super().__init__()
        self._role = role
        self._raw_body = body
        self._render_markdown = render_markdown

    def compose(self) -> ComposeResult:
        role_label = Label(self._role, classes=f"role -{self._role}")
        yield role_label
        if isinstance(self._raw_body, (Markdown, Text)):
            content: object = self._raw_body
        elif self._render_markdown and self._role == "assistant":
            content = Markdown(str(self._raw_body))
        else:
            # Escape so Pydantic/Python error messages with [...] syntax don't
            # get misinterpreted as Rich markup tags and crash the renderer.
            content = markup_escape(str(self._raw_body))
        body = Static(content, classes=f"body -{self._role}")
        yield body


class ChatLog(VerticalScroll):
    """Scrollable container of ChatMessage widgets that auto-scrolls to bottom."""

    DEFAULT_CSS = """
    ChatLog {
        height: 1fr;
        padding: 0 1 1 1;
    }
    """

    async def post_message_block(self, role: str, body: str, *, render_markdown: bool = True) -> None:
        msg = ChatMessage(role, body, render_markdown=render_markdown)
        await self.mount(msg)
        self.scroll_end(animate=False)


class PlanPanel(Static):
    """Sidebar plan view with status glyphs."""

    DEFAULT_CSS = """
    PlanPanel {
        height: auto;
        border: round $accent;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    BORDER_TITLE = "Plan"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Plan"
        self._node_status: dict[str, str] = {}
        self.update(self._format())

    def update_node(self, node_id: str, status: str) -> None:
        self._node_status[node_id] = status
        self.update(self._format())

    def reset(self, ids: Iterable[str] | None = None) -> None:
        self._node_status = {nid: "pending" for nid in (ids or [])}
        self.update(self._format())

    def _format(self) -> str:
        if not self._node_status:
            return "[dim](idle)[/dim]"
        return "\n".join(
            f"  {_STATUS_GLYPH.get(s, '?')} {nid}" for nid, s in self._node_status.items()
        )


class SessionPanel(Static):
    """Cost / token / step counters."""

    DEFAULT_CSS = """
    SessionPanel {
        height: auto;
        border: round $primary;
        padding: 0 1;
        margin-bottom: 1;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Session"
        self.cost_usd = 0.0
        self.in_tokens = 0
        self.out_tokens = 0
        self.steps = 0
        self.deployment = ""
        self.update(self._format())

    def set_summary(
        self,
        cost_usd: float,
        in_tokens: int,
        out_tokens: int,
        steps: int,
        deployment: str = "",
    ) -> None:
        self.cost_usd = cost_usd
        self.in_tokens = in_tokens
        self.out_tokens = out_tokens
        self.steps = steps
        self.deployment = deployment
        self.update(self._format())

    def _format(self) -> str:
        deployment_line = f"  Azure  [b]{self.deployment}[/b]\n" if self.deployment else ""
        return (
            f"{deployment_line}"
            f"  Cost   [b]${self.cost_usd:.4f}[/b]\n"
            f"  Tokens {self.in_tokens} in / {self.out_tokens} out\n"
            f"  Steps  {self.steps}"
        )


class ToolPanel(Static):
    """List of registered tools with risk levels."""

    DEFAULT_CSS = """
    ToolPanel {
        height: auto;
        border: round $secondary;
        padding: 0 1;
    }
    """

    _RISK_COLOR = {"low": "green", "medium": "yellow", "high": "red"}

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.border_title = "Tools"
        self._items: list[tuple[str, str]] = []  # (name, risk)
        self.update("[dim](no tools)[/dim]")

    def set_tools(self, items: Iterable[tuple[str, str]]) -> None:
        self._items = list(items)
        if not self._items:
            self.update("[dim](no tools)[/dim]")
            return
        lines = []
        for name, risk in self._items:
            color = self._RISK_COLOR.get(risk, "white")
            lines.append(f"  • {name}  [{color}]({risk})[/{color}]")
        self.update("\n".join(lines))


class HITLModal(ModalScreen[bool]):
    """Approve/Cancel modal for high-risk tool calls."""

    BINDINGS = [
        Binding("a", "approve", "Approve"),
        Binding("c", "cancel", "Cancel"),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    HITLModal {
        align: center middle;
    }
    #hitl-card {
        width: 60;
        height: auto;
        border: heavy $warning;
        padding: 1 2;
        background: $surface;
    }
    #hitl-buttons {
        height: 3;
        align: center middle;
    }
    """

    def __init__(self, request_id: str, tool_name: str, summary: str) -> None:
        super().__init__()
        self.request_id = request_id
        self.tool_name = tool_name
        self.summary = summary

    def compose(self) -> ComposeResult:
        with Vertical(id="hitl-card"):
            yield Label(f"High-risk tool call: [b]{self.tool_name}[/b]")
            yield Static(self.summary)
            with Horizontal(id="hitl-buttons"):
                yield Button("Approve", id="approve", variant="success")
                yield Button("Cancel", id="cancel", variant="error")

    @on(Button.Pressed, "#approve")
    def _on_approve(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#cancel")
    def _on_cancel(self) -> None:
        self.dismiss(False)

    def action_approve(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class CommandPalette(OptionList):
    """Filterable autocomplete list shown above the input when user types '/'."""

    DEFAULT_CSS = """
    CommandPalette {
        max-height: 8;
        height: auto;
        border: round $accent;
        background: $surface;
        margin: 0 1;
        display: none;
    }
    CommandPalette.-visible { display: block; }
    """

    def __init__(self, commands: Sequence[tuple[str, str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self._all = list(commands)
        self.can_focus = False  # input keeps focus; palette is just a visual aid

    def filter(self, prefix: str) -> bool:
        """Filter options by name prefix. Returns True if any options match."""
        self.clear_options()
        needle = prefix.lstrip("/").lower().split(" ", 1)[0]
        matches = [
            Option(f"/{name}  [dim]— {desc}[/dim]", id=name)
            for name, desc in self._all
            if name.lower().startswith(needle)
        ]
        if not matches:
            self.hide()
            return False
        self.add_options(matches)
        self.highlighted = 0
        self.show()
        return True

    def show(self) -> None:
        self.add_class("-visible")

    def hide(self) -> None:
        self.remove_class("-visible")
        self.clear_options()

    @property
    def is_visible(self) -> bool:
        return self.has_class("-visible")

    def selected_command(self) -> str | None:
        if not self.is_visible or self.highlighted is None:
            return None
        opt = self.get_option_at_index(self.highlighted)
        return opt.id


class CommandInput(Input):
    """Input that delegates ↑/↓/Tab/Esc to a CommandPalette while it's visible."""

    def __init__(self, *args, palette: CommandPalette | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._palette = palette

    def attach_palette(self, palette: CommandPalette) -> None:
        self._palette = palette

    async def _on_key(self, event: events.Key) -> None:  # type: ignore[override]
        p = self._palette
        if p is not None and p.is_visible:
            if event.key == "down":
                p.action_cursor_down()
                event.stop()
                event.prevent_default()
                return
            if event.key == "up":
                p.action_cursor_up()
                event.stop()
                event.prevent_default()
                return
            if event.key == "tab":
                cmd = p.selected_command()
                if cmd is not None:
                    self.value = f"/{cmd} "
                    self.cursor_position = len(self.value)
                    p.hide()
                event.stop()
                event.prevent_default()
                return
            if event.key == "escape":
                p.hide()
                event.stop()
                event.prevent_default()
                return
            if event.key == "enter":
                cmd = p.selected_command()
                if cmd is not None and self.value.lstrip("/").split(" ", 1)[0] != cmd:
                    # User highlighted an option without finishing typing it; commit it.
                    self.value = f"/{cmd}"
                    self.cursor_position = len(self.value)
                p.hide()
                # fall through to default Enter handling (Input.Submitted)
        await super()._on_key(event)


__all__ = [
    "ChatLog",
    "ChatMessage",
    "CommandInput",
    "CommandPalette",
    "HITLModal",
    "PlanPanel",
    "SessionPanel",
    "ToolPanel",
]
