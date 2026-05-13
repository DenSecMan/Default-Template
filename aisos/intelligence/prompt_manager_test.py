"""Tests for prompt template assembly."""

from __future__ import annotations

from pathlib import Path

import pytest

from aisos.intelligence.prompt_manager import PromptManager


def test_render_substitutes_vars(tmp_path: Path) -> None:
    (tmp_path / "greet.md").write_text("hello {who}", encoding="utf-8")
    pm = PromptManager(prompts_dir=tmp_path)
    assert pm.render("greet", who="world") == "hello world"


def test_render_leaves_missing_vars_intact(tmp_path: Path) -> None:
    (tmp_path / "t.md").write_text("a={a} b={b}", encoding="utf-8")
    pm = PromptManager(prompts_dir=tmp_path)
    assert pm.render("t", a="1") == "a=1 b={b}"


def test_missing_template_raises(tmp_path: Path) -> None:
    pm = PromptManager(prompts_dir=tmp_path)
    with pytest.raises(FileNotFoundError):
        pm.render("nope")


def test_list_templates(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("", encoding="utf-8")
    (tmp_path / "b.md").write_text("", encoding="utf-8")
    pm = PromptManager(prompts_dir=tmp_path)
    assert pm.list_templates() == ["a", "b"]


def test_default_prompts_dir_loads_system_template() -> None:
    pm = PromptManager()
    out = pm.render("system", persona="planner", tools="-", task="x")
    assert "planner" in out
