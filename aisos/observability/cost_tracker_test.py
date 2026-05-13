"""Tests for cost tracker math."""

from __future__ import annotations

from pathlib import Path

from aisos.config import load_config
from aisos.observability.cost_tracker import CostTracker


def _cfg(tmp_path: Path) -> object:
    env = tmp_path / ".env"
    env.write_text("", encoding="utf-8")
    toml = tmp_path / "config.toml"
    toml.write_text(
        '[cost]\n'
        '[cost."gpt-4o"]\n'
        'input  = 0.01\n'
        'output = 0.02\n',
        encoding="utf-8",
    )
    return load_config(env_file=env, toml_file=toml)


def test_record_computes_usd(tmp_path: Path) -> None:
    tracker = CostTracker(_cfg(tmp_path))  # type: ignore[arg-type]
    usd = tracker.record("gpt-4o", 1000, 500, agent="planner")
    # 1000/1000 * 0.01 + 500/1000 * 0.02 = 0.01 + 0.01 = 0.02
    assert usd == 0.02


def test_summary_aggregates(tmp_path: Path) -> None:
    tracker = CostTracker(_cfg(tmp_path))  # type: ignore[arg-type]
    tracker.record("gpt-4o", 1000, 0, agent="a")
    tracker.record("gpt-4o", 0, 1000, agent="b")
    s = tracker.summary()
    assert round(s.total.usd, 6) == round(0.01 + 0.02, 6)
    assert s.per_agent["a"].in_tokens == 1000
    assert s.per_agent["b"].out_tokens == 1000


def test_unknown_model_costs_zero(tmp_path: Path) -> None:
    tracker = CostTracker(_cfg(tmp_path))  # type: ignore[arg-type]
    usd = tracker.record("mystery-model", 9999, 9999)
    assert usd == 0.0
