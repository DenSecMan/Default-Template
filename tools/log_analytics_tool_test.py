"""Tests for LogAnalyticsQueryTool with a mocked SDK client."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tools import log_analytics_tool as la
from tools.log_analytics_tool import (
    LogAnalyticsConfigError,
    LogAnalyticsQueryInput,
    LogAnalyticsQueryTool,
    _serialize,
)


def _set_env(monkeypatch, **values: str) -> None:
    for k, v in values.items():
        monkeypatch.setenv(k, v)


class _FakeClient:
    """Records the call args; returns a configured fake response."""

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
async def test_runs_kql_and_serialises_rows(monkeypatch) -> None:
    _set_env(
        monkeypatch,
        AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", AZURE_CLIENT_SECRET="s",
        AZURE_WORKSPACE_ID="ws-1",
    )
    fake_resp = _fake_response(
        [_fake_table("PrimaryResult", ["TimeGenerated", "Count"],
                     [["2026-01-01T00:00:00Z", 7]])]
    )
    fake_client = _FakeClient(fake_resp)
    monkeypatch.setattr(la, "_build_client", lambda: fake_client)

    tool = LogAnalyticsQueryTool()
    payload = LogAnalyticsQueryInput(kql="SecurityEvent | take 1", timespan_hours=1)
    out = await tool.run(payload)

    assert fake_client.calls[0]["workspace_id"] == "ws-1"
    assert fake_client.calls[0]["query"] == "SecurityEvent | take 1"
    table = out["tables"][0]
    assert table["name"] == "PrimaryResult"
    assert table["row_count"] == 1
    assert table["rows"] == [{"TimeGenerated": "2026-01-01T00:00:00Z", "Count": 7}]
    assert table["truncated"] is False


@pytest.mark.asyncio
async def test_workspace_id_arg_overrides_env(monkeypatch) -> None:
    _set_env(
        monkeypatch,
        AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", AZURE_CLIENT_SECRET="s",
        AZURE_WORKSPACE_ID="env-ws",
    )
    fake_client = _FakeClient(_fake_response([_fake_table("R", [], [])]))
    monkeypatch.setattr(la, "_build_client", lambda: fake_client)

    await LogAnalyticsQueryTool().run(
        LogAnalyticsQueryInput(kql="print 1", workspace_id="override-ws")
    )
    assert fake_client.calls[0]["workspace_id"] == "override-ws"


@pytest.mark.asyncio
async def test_truncates_rows_to_max(monkeypatch) -> None:
    _set_env(
        monkeypatch,
        AZURE_TENANT_ID="t", AZURE_CLIENT_ID="c", AZURE_CLIENT_SECRET="s",
        AZURE_WORKSPACE_ID="ws",
    )
    rows = [[i] for i in range(50)]
    fake_client = _FakeClient(
        _fake_response([_fake_table("R", ["i"], rows)])
    )
    monkeypatch.setattr(la, "_build_client", lambda: fake_client)

    out = await LogAnalyticsQueryTool().run(
        LogAnalyticsQueryInput(kql="x", max_rows=10)
    )
    table = out["tables"][0]
    assert table["row_count"] == 10
    assert table["truncated"] is True


@pytest.mark.asyncio
async def test_missing_credentials_raises(monkeypatch) -> None:
    for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_WORKSPACE_ID"):
        monkeypatch.delenv(k, raising=False)
    tool = LogAnalyticsQueryTool()
    with pytest.raises(LogAnalyticsConfigError):
        await tool.run(LogAnalyticsQueryInput(kql="print 1"))


def test_serialize_handles_non_jsonable_values() -> None:
    from datetime import datetime, UTC
    table = _fake_table(
        "T", ["ts", "obj"],
        [[datetime(2026, 5, 1, tzinfo=UTC), object()]],
    )
    out = _serialize(_fake_response([table]), max_rows=10)
    row = out["tables"][0]["rows"][0]
    assert isinstance(row["ts"], str)
    assert isinstance(row["obj"], str)
