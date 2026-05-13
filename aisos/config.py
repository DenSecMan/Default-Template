"""Configuration loader: merges environment (.env) + config.toml."""

from __future__ import annotations

import sys
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RoutingRule(BaseModel):
    provider: str
    model: str = ""  # empty => provider falls back to its env-configured deployment


class CostEntry(BaseModel):
    input: float = 0.0
    output: float = 0.0


class TomlConfig(BaseModel):
    """Schema for config.toml."""

    max_steps: int = 25
    routing: dict[str, RoutingRule] = Field(default_factory=dict)
    rbac: dict[str, list[str]] = Field(default_factory=dict)
    cost: dict[str, CostEntry] = Field(default_factory=dict)


class Settings(BaseSettings):
    """Environment-backed settings (.env)."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_deployment_chat: str = "gpt-4o"
    azure_openai_deployment_embed: str = "text-embedding-3-small"

    aisos_db_path: str = "./aisos.db"
    aisos_config_path: str = "./config.toml"


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("rb") as fh:
        return tomllib.load(fh)


class AppConfig(BaseModel):
    """Combined runtime config: env settings + toml config."""

    settings: Settings
    toml: TomlConfig

    @property
    def db_path(self) -> Path:
        return Path(self.settings.aisos_db_path)


def load_config(
    env_file: str | Path | None = None,
    toml_file: str | Path | None = None,
) -> AppConfig:
    """Load Settings + TomlConfig and combine them."""
    if env_file is not None:
        settings = Settings(_env_file=str(env_file))  # type: ignore[call-arg]
    else:
        settings = Settings()
    toml_path = Path(toml_file) if toml_file else Path(settings.aisos_config_path)
    raw = _load_toml(toml_path)
    toml = TomlConfig.model_validate(raw)
    return AppConfig(settings=settings, toml=toml)


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Process-level cached config."""
    return load_config()


__all__ = [
    "AppConfig",
    "CostEntry",
    "RoutingRule",
    "Settings",
    "TomlConfig",
    "get_config",
    "load_config",
]


if sys.version_info < (3, 11):  # pragma: no cover - guarded by pyproject
    raise RuntimeError("AISOS requires Python 3.11+ (tomllib).")
