"""Tests for aisos.config."""

from __future__ import annotations

from pathlib import Path

from aisos.config import AppConfig, load_config


def test_load_config_with_project_files(tmp_path: Path, monkeypatch) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "AZURE_OPENAI_ENDPOINT=https://x\n"
        "AZURE_OPENAI_API_KEY=k\n"
        "AISOS_DB_PATH=./test.db\n",
        encoding="utf-8",
    )
    toml = tmp_path / "config.toml"
    toml.write_text(
        'max_steps = 7\n'
        '[routing]\n'
        'default = { provider = "azure_openai", model = "gpt-4o" }\n'
        '[rbac]\n'
        'planner = ["read"]\n'
        '[cost]\n'
        '[cost."gpt-4o"]\n'
        'input = 0.001\n'
        'output = 0.002\n',
        encoding="utf-8",
    )
    cfg: AppConfig = load_config(env_file=env, toml_file=toml)
    assert cfg.settings.azure_openai_endpoint == "https://x"
    assert cfg.settings.azure_openai_api_key == "k"
    assert cfg.toml.max_steps == 7
    assert cfg.toml.routing["default"].model == "gpt-4o"
    assert cfg.toml.rbac["planner"] == ["read"]
    assert cfg.toml.cost["gpt-4o"].input == 0.001
    assert cfg.db_path == Path("./test.db")


def test_load_config_missing_toml_uses_defaults(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("AISOS_DB_PATH=./other.db\n", encoding="utf-8")
    cfg = load_config(env_file=env, toml_file=tmp_path / "missing.toml")
    assert cfg.toml.max_steps == 25
    assert cfg.toml.routing == {}
    assert cfg.db_path == Path("./other.db")
