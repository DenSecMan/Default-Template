"""AISOS entry point. Run with `uv run aisos`."""

from __future__ import annotations

import asyncio
import sys

from aisos.logging_setup import configure_logging


def _set_windows_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def main() -> int:
    """Entry point for `aisos` console script."""
    _set_windows_event_loop_policy()
    configure_logging(log_file="aisos.debug.log")

    from aisos.tui.app import AISOSApp

    AISOSApp().run()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
