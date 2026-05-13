"""VirusTotalTool: look up IPs, domains, URLs, and file hashes via VirusTotal API v3."""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from aisos.config import get_config
from aisos.tools.base import BaseTool

_BASE = "https://www.virustotal.com/api/v3"

IndicatorType = Literal["ip", "domain", "url", "file"]


class VirusTotalInput(BaseModel):
    indicator: str = Field(
        ...,
        description=(
            "The value to look up: an IPv4/IPv6 address, domain name, URL, "
            "or SHA-256/MD5/SHA-1 file hash."
        ),
    )
    indicator_type: IndicatorType = Field(
        ...,
        description=(
            "Type of indicator: 'ip', 'domain', 'url', or 'file'. "
            "URLs are base64url-encoded by the tool automatically."
        ),
    )


def _api_key() -> str:
    key = get_config().settings.virustotal_api_key
    if not key:
        raise RuntimeError(
            "VIRUSTOTAL_API_KEY is not configured. Add it to your .env file."
        )
    return key


def _endpoint(indicator_type: IndicatorType, indicator: str) -> str:
    import base64
    if indicator_type == "ip":
        return f"{_BASE}/ip_addresses/{indicator}"
    if indicator_type == "domain":
        return f"{_BASE}/domains/{indicator}"
    if indicator_type == "url":
        encoded = base64.urlsafe_b64encode(indicator.encode()).rstrip(b"=").decode()
        return f"{_BASE}/urls/{encoded}"
    return f"{_BASE}/files/{indicator}"


def _summarise(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the most useful fields from a VT response attributes block."""
    attrs = data.get("data", {}).get("attributes", {})
    stats = attrs.get("last_analysis_stats", {})
    return {
        "id": data.get("data", {}).get("id"),
        "type": data.get("data", {}).get("type"),
        "malicious": stats.get("malicious", 0),
        "suspicious": stats.get("suspicious", 0),
        "harmless": stats.get("harmless", 0),
        "undetected": stats.get("undetected", 0),
        "reputation": attrs.get("reputation"),
        "country": attrs.get("country"),
        "as_owner": attrs.get("as_owner"),
        "network": attrs.get("network"),
        "last_analysis_date": attrs.get("last_analysis_date"),
        "tags": attrs.get("tags", []),
        "categories": attrs.get("categories", {}),
    }


class VirusTotalTool(BaseTool):
    name = "virustotal_lookup"
    description = (
        "Look up an IP address, domain, URL, or file hash against VirusTotal. "
        "Returns malicious/suspicious/harmless engine vote counts, reputation score, "
        "country, ASN, and tags. Use for threat intelligence on indicators of compromise."
    )
    input_schema = VirusTotalInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: VirusTotalInput) -> dict[str, Any]:  # type: ignore[override]
        url = _endpoint(input.indicator_type, input.indicator)
        headers = {"x-apikey": _api_key(), "Accept": "application/json"}
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
        if resp.status_code == 404:
            return {"indicator": input.indicator, "found": False}
        resp.raise_for_status()
        return {"indicator": input.indicator, "found": True, **_summarise(resp.json())}


__all__ = ["VirusTotalInput", "VirusTotalTool"]
