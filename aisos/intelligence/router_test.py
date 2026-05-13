"""Tests for intelligence.router selection logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from aisos.config import load_config
from aisos.intelligence.base_test import MockProvider
from aisos.intelligence.router import Router


def _cfg(tmp_path: Path) -> object:
    env = tmp_path / ".env"
    env.write_text("AZURE_OPENAI_API_KEY=k\n", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[routing]\n'
        'default = { provider = "mock", model = "alpha" }\n'
        'plan    = { provider = "mock", model = "beta" }\n'
        'embed   = { provider = "other", model = "gamma" }\n',
        encoding="utf-8",
    )
    return load_config(env_file=env, toml_file=toml)


def test_route_known_capability(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    mock = MockProvider()
    router = Router(cfg, {"mock": mock})  # type: ignore[arg-type]
    r = router.route("plan")
    assert r.model == "beta"
    assert r.provider is mock


def test_route_falls_back_to_default(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    router = Router(cfg, {"mock": MockProvider()})  # type: ignore[arg-type]
    r = router.route("nonexistent_capability")
    assert r.model == "alpha"


def test_route_missing_provider_raises(tmp_path: Path) -> None:
    cfg = _cfg(tmp_path)
    router = Router(cfg, {"mock": MockProvider()})  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        router.route("embed")  # 'other' provider not registered


def test_route_no_default_no_match_raises(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[routing]\n'
        'plan = { provider = "mock", model = "beta" }\n',
        encoding="utf-8",
    )
    cfg = load_config(env_file=env, toml_file=toml)
    router = Router(cfg, {"mock": MockProvider()})  # type: ignore[arg-type]
    with pytest.raises(KeyError):
        router.route("unknown")
