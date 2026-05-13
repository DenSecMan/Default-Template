"""Textual app shell. Real layout & widgets land in task 6.0."""

from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class AISOSApp(App[int]):
    """Top-level AISOS Textual app."""

    TITLE = "AISOS"
    SUB_TITLE = "Agentic Intelligence Shell OS"
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("AISOS shell — scaffolding only. (q to quit)", id="placeholder")
        yield Footer()
