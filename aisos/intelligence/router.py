"""Capability/cost-based provider+model selection."""

from __future__ import annotations

from dataclasses import dataclass

from aisos.config import AppConfig, RoutingRule
from aisos.intelligence.base import BaseLLMProvider


@dataclass
class Route:
    provider: BaseLLMProvider
    model: str


class Router:
    """Map a capability string to (provider, model) using config.toml [routing]."""

    DEFAULT_KEY = "default"

    def __init__(
        self, config: AppConfig, providers: dict[str, BaseLLMProvider]
    ) -> None:
        self._config = config
        self._providers = providers

    def _rule_for(self, capability: str) -> RoutingRule:
        rules = self._config.toml.routing
        if capability in rules:
            return rules[capability]
        if self.DEFAULT_KEY in rules:
            return rules[self.DEFAULT_KEY]
        raise KeyError(f"No routing rule for capability '{capability}' and no default.")

    def route(self, capability: str) -> Route:
        rule = self._rule_for(capability)
        provider = self._providers.get(rule.provider)
        if provider is None:
            raise KeyError(f"No provider registered under '{rule.provider}'.")
        return Route(provider=provider, model=rule.model)


__all__ = ["Route", "Router"]
