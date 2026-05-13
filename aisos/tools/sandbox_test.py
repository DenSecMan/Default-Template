"""Tests for tools.sandbox."""

from __future__ import annotations

import pytest

from aisos.tools.sandbox import SandboxTimeout, run_python


def test_runs_simple_script() -> None:
    r = run_python("print(40 + 2)")
    assert r.returncode == 0
    assert r.stdout.strip() == "42"


def test_timeout_kills_long_running_script() -> None:
    with pytest.raises(SandboxTimeout):
        run_python("import time; time.sleep(10)", timeout_s=0.5)


def test_isolated_mode_blocks_user_site() -> None:
    # In -I mode sys.flags.isolated should be 1
    r = run_python("import sys; print(sys.flags.isolated)")
    assert r.stdout.strip() == "1"
