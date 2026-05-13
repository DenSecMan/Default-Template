"""Tests for RBAC scope enforcement."""

from __future__ import annotations

from pathlib import Path

import pytest

from aisos.config import load_config
from aisos.security.rbac import RBACDenied, check


def _cfg(tmp_path: Path) -> object:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[rbac]\n'
        'planner = ["read", "write"]\n'
        'reader  = ["read"]\n'
        'default = ["read"]\n',
        encoding="utf-8",
    )
    return load_config(env_file=env, toml_file=toml)


def test_allows_in_scope(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    check(cfg, "planner", "write")  # type: ignore[arg-type]


def test_blocks_out_of_scope(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    with pytest.raises(RBACDenied):
        check(cfg, "reader", "write")  # type: ignore[arg-type]


def test_unknown_agent_falls_back_to_default(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    check(cfg, "unknown_agent", "read")  # type: ignore[arg-type]
    with pytest.raises(RBACDenied):
        check(cfg, "unknown_agent", "write")  # type: ignore[arg-type]
