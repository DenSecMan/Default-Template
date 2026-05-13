"""Tests for LogAnalyticsDescribeTableTool."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from tools import log_analytics_tool as la
from tools.log_analytics_describe_tool import (
    LogAnalyticsDescribeInput,
    LogAnalyticsDescribeTableTool,
)


def _set_env(monkeypatch, **values: str) -> None:
    for k, v in values.items():
        monkeypatch.setenv(k, v)


class _FakeClient:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict[str, Any]] = []

    async def query_workspace(self, **kwargs):
        self.calls.append(kwargs)
        return self.response

    async def close(self) -> None:
        return None


def _fake_table(name: str, columns: list[str], rows: list[list[Any]]):
    return SimpleNamespace(name=name, columns=columns, rows=rows)


def _fake_response(tables, status="Success", partial_error=None):
    return SimpleNamespace(tables=tables, status=status, partial_error=partial_error)


@pytest.mark.asyncio
async def test_runs_getschema_and_flattens_columns(monkeypatch) -> None:
    _set_env(
        monkeypatch,
        AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", AZURE_CLIENT_SECRET="s",
        AZURE_WORKSPACE_ID="ws-1",
    )
    fake_resp = _fake_response(
        [_fake_table("PrimaryResult", ["ColumnName", "DataType"], [
            ["TimeGenerated", "datetime"],
            ["Account", "string"],
            ["EventID", "int"],
        ])]
    )
    fake_client = _FakeClient(fake_resp)
    monkeypatch.setattr(la, "_build_client", lambda: fake_client)

    out = await LogAnalyticsDescribeTableTool().run(
        LogAnalyticsDescribeInput(table="SecurityEvent")
    )

    sent_kql = fake_client.calls[0]["query"]
    assert sent_kql == "SecurityEvent | getschema | project ColumnName, DataType"
    assert out["table"] == "SecurityEvent"
    assert out["column_count"] == 3
    assert out["columns"] == [
        {"name": "TimeGenerated", "type": "datetime"},
        {"name": "Account", "type": "string"},
        {"name": "EventID", "type": "int"},
    ]


def test_table_name_validation_rejects_kql_injection() -> None:
    # leading char must be a letter, no whitespace or operators allowed
    for bad in ["1Table", "Table; drop", "Foo Bar", "Foo|bar", "", "Foo'", "../etc"]:
        with pytest.raises(ValidationError):
            LogAnalyticsDescribeInput(table=bad)


def test_table_name_validation_accepts_real_names() -> None:
    for good in ["SecurityEvent", "SigninLogs", "AzureActivity", "MyCustom_CL", "T1", "AuditLogs"]:
        # must not raise
        LogAnalyticsDescribeInput(table=good)


@pytest.mark.asyncio
async def test_workspace_override(monkeypatch) -> None:
    _set_env(
        monkeypatch,
        AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", AZURE_CLIENT_SECRET="s",
        AZURE_WORKSPACE_ID="env-ws",
    )
    fake_client = _FakeClient(_fake_response([_fake_table("R", [], [])]))
    monkeypatch.setattr(la, "_build_client", lambda: fake_client)

    await LogAnalyticsDescribeTableTool().run(
        LogAnalyticsDescribeInput(table="SigninLogs", workspace_id="explicit-ws")
    )
    assert fake_client.calls[0]["workspace_id"] == "explicit-ws"
