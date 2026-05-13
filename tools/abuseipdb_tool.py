"""AbuseIPDBTool: check IP reputation and abuse reports via AbuseIPDB v2 API."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from aisos.config import get_config
from aisos.tools.base import BaseTool

_BASE = "https://api.abuseipdb.com/api/v2"


class AbuseIPDBInput(BaseModel):
    ip_address: str = Field(..., description="IPv4 or IPv6 address to check.")
    max_age_days: int = Field(
        30,
        ge=1,
        le=365,
        description="Only include reports from the last N days (1–365, default 30).",
    )
    verbose: bool = Field(
        False,
        description="Set True to include the most recent individual abuse reports.",
    )


def _api_key() -> str:
    key = get_config().settings.abuseipdb_api_key
    if not key:
        raise RuntimeError(
            "ABUSEIPDB_API_KEY is not configured. Add it to your .env file."
        )
    return key


class AbuseIPDBTool(BaseTool):
    name = "abuseipdb_check"
    description = (
        "Check an IP address against AbuseIPDB for abuse reports and confidence score. "
        "Returns the abuse-confidence percentage (0–100), ISP, usage type, country, "
        "total report count, and optionally recent report summaries. "
        "Use for rapid IP triage during incident response."
    )
    input_schema = AbuseIPDBInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: AbuseIPDBInput) -> dict[str, Any]:  # type: ignore[override]
        params: dict[str, Any] = {
            "ipAddress": input.ip_address,
            "maxAgeInDays": input.max_age_days,
        }
        if input.verbose:
            params["verbose"] = True

        headers = {"Key": _api_key(), "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{_BASE}/check", headers=headers, params=params)

        if resp.status_code == 422:
            return {"ip_address": input.ip_address, "error": "Invalid IP address format"}
        resp.raise_for_status()

        data = resp.json().get("data", {})
        result: dict[str, Any] = {
            "ip_address": data.get("ipAddress"),
            "is_public": data.get("isPublic"),
            "ip_version": data.get("ipVersion"),
            "is_whitelisted": data.get("isWhitelisted"),
            "abuse_confidence_score": data.get("abuseConfidenceScore"),
            "country_code": data.get("countryCode"),
            "usage_type": data.get("usageType"),
            "isp": data.get("isp"),
            "domain": data.get("domain"),
            "total_reports": data.get("totalReports"),
            "num_distinct_users": data.get("numDistinctUsers"),
            "last_reported_at": data.get("lastReportedAt"),
        }
        if input.verbose and "reports" in data:
            result["recent_reports"] = [
                {
                    "reported_at": r.get("reportedAt"),
                    "comment": r.get("comment", "")[:300],
                    "categories": r.get("categories", []),
                }
                for r in data["reports"][:10]
            ]
        return result


__all__ = ["AbuseIPDBInput", "AbuseIPDBTool"]
