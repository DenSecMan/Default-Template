"""RBAC: agent scope -> tool permission check (config.toml [rbac])."""

from __future__ import annotations

import logging

from aisos.config import AppConfig

logger = logging.getLogger("aisos.security.rbac")

DEFAULT_AGENT_KEY = "default"


class RBACDenied(PermissionError):
    """Agent attempted a tool whose required scope it lacks."""


def _scopes_for(config: AppConfig, agent_name: str) -> list[str]:
    rbac = config.toml.rbac
    if agent_name in rbac:
        return rbac[agent_name]
    return rbac.get(DEFAULT_AGENT_KEY, [])


def check(config: AppConfig, agent_name: str, required_scope: str) -> None:
    """Raise RBACDenied (and log) if `agent_name` lacks `required_scope`."""
    allowed = _scopes_for(config, agent_name)
    if required_scope not in allowed:
        logger.warning(
            "rbac_denied",
            extra={
                "agent_name": agent_name,
                "required_scope": required_scope,
                "allowed": allowed,
            },
        )
        raise RBACDenied(
            f"Agent '{agent_name}' lacks required scope '{required_scope}' "
            f"(allowed: {allowed})"
        )


__all__ = ["RBACDenied", "check"]
