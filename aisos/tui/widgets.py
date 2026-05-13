"""TUI widgets: streaming output, HITL modal, trace panel."""

from __future__ import annotations

from typing import AsyncIterator, Iterable

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, RichLog, Static

_STATUS_GLYPH = {
    "pending": "·",
    "running": ">",
    "complete": "✓",
    "failed": "x",
}


class StreamingOutput(RichLog):
    """Scrollable log buffer that consumes async iterators of token deltas."""

    DEFAULT_CSS = """
    StreamingOutput {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs, highlight=False, markup=True, wrap=True)

    async def consume_stream(self, stream: AsyncIterator[str]) -> str:
        """Append every chunk yielded; return the concatenated text."""
        buf: list[str] = []
        async for chunk in stream:
            buf.append(chunk)
            self.write(chunk, expand=True)
        return "".join(buf)

    def append_block(self, text: str) -> None:
        self.write(text)


class TracePanel(Static):
    """Renders a text DAG of plan steps with status glyphs."""

    DEFAULT_CSS = """
    TracePanel {
        height: auto;
        border: round $accent;
        padding: 0 1;
    }
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._node_status: dict[str, str] = {}

    def update_node(self, node_id: str, status: str) -> None:
        self._node_status[node_id] = status
        self._redraw()

    def reset(self, ids: Iterable[str] | None = None) -> None:
        self._node_status = {nid: "pending" for nid in (ids or [])}
        self._redraw()

    def _redraw(self) -> None:
        if not self._node_status:
            self.update("(no plan yet)")
            return
        rows = [
            f"  {_STATUS_GLYPH.get(status, '?')} {nid} [{status}]"
            for nid, status in self._node_status.items()
        ]
        self.update("Plan:\n" + "\n".join(rows))


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


__all__ = ["HITLModal", "StreamingOutput", "TracePanel"]
