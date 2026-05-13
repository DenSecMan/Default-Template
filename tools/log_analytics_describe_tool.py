"""LogAnalyticsDescribeTableTool: list columns + types for a Log Analytics table.

Cheap schema discovery — runs `<TableName> | getschema | project ColumnName, DataType | take 0`
under the hood, so the planner can shape downstream KQL without paying a full scan.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from pydantic import BaseModel, Field, field_validator

from aisos.tools.base import BaseTool
from tools import log_analytics_tool as _la
from tools.log_analytics_tool import LogAnalyticsConfigError

_TABLE_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,99}$")


class LogAnalyticsDescribeInput(BaseModel):
    table: str = Field(
        ...,
        description=(
            "Log Analytics table name to describe (e.g. 'SecurityEvent', "
            "'SigninLogs', 'AzureActivity'). Letters, digits, underscores only."
        ),
    )
    workspace_id: str | None = Field(
        None,
        description="Override AZURE_WORKSPACE_ID. Leave null for the env-configured workspace.",
    )

    @field_validator("table")
    @classmethod
    def _validate_table(cls, v: str) -> str:
        if not _TABLE_NAME_RE.match(v):
            raise ValueError(
                "table must be a simple Log Analytics table name "
                "(letters, digits, underscores; starts with a letter)"
            )
        return v


class LogAnalyticsDescribeTableTool(BaseTool):
    name = "log_analytics_describe_table"
    description = (
        "Return the column names and data types for a Log Analytics table. Use this "
        "before writing a query against an unfamiliar table so the KQL references "
        "real columns. Cheap (no row scan)."
    )
    input_schema = LogAnalyticsDescribeInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: LogAnalyticsDescribeInput) -> dict[str, Any]:  # type: ignore[override]
        workspace = _la._resolve_workspace(input.workspace_id)
        credential = _la._build_credential()
        kql = f"{input.table} | getschema | project ColumnName, DataType"
        try:
            from azure.monitor.query.aio import LogsQueryClient
            async with LogsQueryClient(credential) as client:
                response = await client.query_workspace(
                    workspace_id=workspace,
                    query=kql,
                    timespan=timedelta(hours=1),
                )
                payload = _la._serialize(response, max_rows=500)
        finally:
            await credential.close()

        columns: list[dict[str, str]] = []
        for table in payload.get("tables", []):
            for row in table.get("rows", []):
                name = row.get("ColumnName")
                dtype = row.get("DataType")
                if name:
                    columns.append({"name": str(name), "type": str(dtype) if dtype else ""})
        return {"table": input.table, "columns": columns, "column_count": len(columns)}


__all__ = [
    "LogAnalyticsConfigError",
    "LogAnalyticsDescribeInput",
    "LogAnalyticsDescribeTableTool",
]
