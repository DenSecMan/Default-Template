"""LogAnalyticsQueryTool: execute KQL against an Azure Log Analytics workspace.

Auth via Service Principal (AZURE_TENANT_ID / AZURE_CLIENT_ID / AZURE_CLIENT_SECRET).
Target workspace via AZURE_WORKSPACE_ID.

The planner is expected to write the KQL itself. For schema discovery the planner
can issue a `<TableName> | getschema | project ColumnName, ColumnType` query, or
`union withsource=T * | distinct T` (expensive on large workspaces).
"""

from __future__ import annotations

import os
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field

from aisos.config import get_config
from aisos.tools.base import BaseTool


class LogAnalyticsQueryInput(BaseModel):
    kql: str = Field(..., description="KQL query string to execute.")
    timespan_hours: float = Field(
        24.0,
        description=(
            "Look-back window in hours (e.g. 24 = last day). "
            "Use a small window for ad-hoc exploration."
        ),
    )
    workspace_id: str | None = Field(
        None,
        description=(
            "Override the workspace id from AZURE_WORKSPACE_ID. "
            "Leave null to use the env-configured workspace."
        ),
    )
    max_rows: int = Field(
        500, description="Truncate result rows after this many (defensive cap)."
    )


class LogAnalyticsConfigError(RuntimeError):
    """Raised when required env vars / SDK deps are missing."""


def _build_credential():
    s = get_config().settings
    tenant = s.azure_tenant_id or os.environ.get("AZURE_TENANT_ID", "")
    client_id = s.azure_client_id or os.environ.get("AZURE_CLIENT_ID", "")
    secret = s.azure_client_secret or os.environ.get("AZURE_CLIENT_SECRET", "")
    missing = [n for n, v in (
        ("AZURE_TENANT_ID", tenant),
        ("AZURE_CLIENT_ID", client_id),
        ("AZURE_CLIENT_SECRET", secret),
    ) if not v]
    if missing:
        raise LogAnalyticsConfigError(
            f"Missing required env vars for Log Analytics: {', '.join(missing)}"
        )
    try:
        from azure.identity.aio import ClientSecretCredential
    except ImportError as e:  # pragma: no cover
        raise LogAnalyticsConfigError(
            "azure-identity not installed (uv add azure-identity)"
        ) from e
    return ClientSecretCredential(
        tenant_id=tenant, client_id=client_id, client_secret=secret
    )


def _build_client():
    try:
        from azure.monitor.query.aio import LogsQueryClient
    except ImportError as e:  # pragma: no cover
        raise LogAnalyticsConfigError(
            "azure-monitor-query not installed (uv add azure-monitor-query)"
        ) from e
    return LogsQueryClient(_build_credential())


def _resolve_workspace(override: str | None) -> str:
    ws = override or get_config().settings.azure_workspace_id or os.environ.get("AZURE_WORKSPACE_ID", "")
    if not ws:
        raise LogAnalyticsConfigError(
            "No workspace id (set AZURE_WORKSPACE_ID or pass workspace_id arg)"
        )
    return ws


def _serialize(response, max_rows: int) -> dict[str, Any]:
    """Coerce the SDK response into JSON-serialisable rows."""
    from azure.monitor.query import LogsQueryStatus  # local import; SDK may be absent in tests

    status = getattr(response, "status", None)
    tables_out: list[dict[str, Any]] = []
    for table in getattr(response, "tables", []) or []:
        cols = list(getattr(table, "columns", []) or [])
        rows = list(getattr(table, "rows", []) or [])
        truncated = len(rows) > max_rows
        rows = rows[:max_rows]
        # Each row is a sequence aligned with cols; convert to dict per row.
        rows_dicts = [
            {col: _stringify(value) for col, value in zip(cols, row, strict=False)}
            for row in rows
        ]
        tables_out.append(
            {
                "name": getattr(table, "name", ""),
                "columns": cols,
                "row_count": len(rows_dicts),
                "truncated": truncated,
                "rows": rows_dicts,
            }
        )
    payload: dict[str, Any] = {"tables": tables_out}
    if status is not None:
        payload["status"] = str(status)
        if status == LogsQueryStatus.PARTIAL:
            err = getattr(response, "partial_error", None)
            payload["partial_error"] = str(err) if err else None
    return payload


def _stringify(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


class LogAnalyticsQueryTool(BaseTool):
    name = "log_analytics_query"
    description = (
        "Execute a KQL (Kusto Query Language) query against the configured Azure "
        "Log Analytics workspace and return rows as JSON. Use for Sentinel data, "
        "AzureActivity, SigninLogs, SecurityEvent, custom logs, etc. The planner "
        "writes the KQL directly; for schema discovery, query "
        "'<TableName> | getschema | project ColumnName, ColumnType'."
    )
    input_schema = LogAnalyticsQueryInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: LogAnalyticsQueryInput) -> dict[str, Any]:  # type: ignore[override]
        workspace = _resolve_workspace(input.workspace_id)
        credential = _build_credential()
        try:
            from azure.monitor.query.aio import LogsQueryClient
            async with LogsQueryClient(credential) as client:
                response = await client.query_workspace(
                    workspace_id=workspace,
                    query=input.kql,
                    timespan=timedelta(hours=input.timespan_hours),
                )
                return _serialize(response, input.max_rows)
        finally:
            await credential.close()


__all__ = [
    "LogAnalyticsConfigError",
    "LogAnalyticsQueryInput",
    "LogAnalyticsQueryTool",
]
