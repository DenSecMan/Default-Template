"""Modular prompt template assembler. Loads templates from aisos/prompts/*.md."""

from __future__ import annotations

import string
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class _SafeFormatter(string.Formatter):
    """Format string that leaves missing keys as '{key}' instead of raising."""

    def get_value(self, key, args, kwargs):  # type: ignore[override]
        if isinstance(key, str):
            return kwargs.get(key, "{" + key + "}")
        return super().get_value(key, args, kwargs)


class PromptManager:
    """Load + render prompt templates."""

    def __init__(self, prompts_dir: Path | None = None) -> None:
        self._dir = prompts_dir or PROMPTS_DIR
        self._cache: dict[str, str] = {}
        self._fmt = _SafeFormatter()

    def _load(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]
        path = self._dir / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template '{name}' not found at {path}")
        text = path.read_text(encoding="utf-8")
        self._cache[name] = text
        return text

    def render(self, name: str, **vars: object) -> str:
        template = self._load(name)
        return self._fmt.format(template, **vars)

    def list_templates(self) -> list[str]:
        return sorted(p.stem for p in self._dir.glob("*.md"))


__all__ = ["PROMPTS_DIR", "PromptManager"]
