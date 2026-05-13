"""Per-agent + total token & USD accumulator."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from aisos.config import AppConfig, CostEntry


@dataclass
class CostBucket:
    in_tokens: int = 0
    out_tokens: int = 0
    usd: float = 0.0


@dataclass
class CostSummary:
    per_agent: dict[str, CostBucket] = field(default_factory=dict)
    per_model: dict[str, CostBucket] = field(default_factory=dict)
    total: CostBucket = field(default_factory=CostBucket)


class CostTracker:
    """Compute USD using the [cost.<model>] table from config.toml."""

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._per_agent: dict[str, CostBucket] = defaultdict(CostBucket)
        self._per_model: dict[str, CostBucket] = defaultdict(CostBucket)
        self._total = CostBucket()

    def _price(self, model: str) -> CostEntry:
        return self._config.toml.cost.get(model, CostEntry(input=0.0, output=0.0))

    def record(
        self,
        model: str,
        in_tokens: int,
        out_tokens: int,
        agent: str = "default",
    ) -> float:
        price = self._price(model)
        usd = (in_tokens / 1000.0) * price.input + (out_tokens / 1000.0) * price.output
        for bucket in (
            self._per_agent[agent],
            self._per_model[model],
            self._total,
        ):
            bucket.in_tokens += in_tokens
            bucket.out_tokens += out_tokens
            bucket.usd += usd
        return usd

    def summary(self) -> CostSummary:
        return CostSummary(
            per_agent=dict(self._per_agent),
            per_model=dict(self._per_model),
            total=self._total,
        )


__all__ = ["CostBucket", "CostSummary", "CostTracker"]
