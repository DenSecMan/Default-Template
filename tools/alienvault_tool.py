"""AlienVaultTool: query AlienVault OTX for threat intelligence on IPs, domains, and hashes."""

from __future__ import annotations

from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from aisos.config import get_config
from aisos.tools.base import BaseTool

_BASE = "https://otx.alienvault.com/api/v1"

IndicatorType = Literal["ip", "domain", "hostname", "url", "file_hash"]


class AlienVaultInput(BaseModel):
    indicator: str = Field(
        ...,
        description=(
            "The indicator value: IPv4/IPv6, domain, hostname, URL, "
            "or MD5/SHA1/SHA256 file hash."
        ),
    )
    indicator_type: IndicatorType = Field(
        ...,
        description=(
            "Type: 'ip', 'domain', 'hostname', 'url', or 'file_hash'."
        ),
    )


def _api_key() -> str:
    key = get_config().settings.alienvault_otx_api_key
    if not key:
        raise RuntimeError(
            "ALIENVAULT_OTX_API_KEY is not configured. Add it to your .env file."
        )
    return key


_TYPE_PATH: dict[str, str] = {
    "ip": "IPv4",
    "domain": "domain",
    "hostname": "hostname",
    "url": "url",
    "file_hash": "file",
}


async def _fetch_section(
    client: httpx.AsyncClient,
    indicator_type: str,
    indicator: str,
    section: str,
    headers: dict[str, str],
) -> dict[str, Any]:
    path = _TYPE_PATH[indicator_type]
    url = f"{_BASE}/indicators/{path}/{indicator}/{section}"
    resp = await client.get(url, headers=headers)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    return resp.json()


class AlienVaultTool(BaseTool):
    name = "alienvault_lookup"
    description = (
        "Look up an IP, domain, hostname, URL, or file hash in AlienVault OTX. "
        "Returns pulse count (community threat reports), threat score, associated malware "
        "families, and geo/ASN data for IPs. Use for threat intelligence enrichment."
    )
    input_schema = AlienVaultInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: AlienVaultInput) -> dict[str, Any]:  # type: ignore[override]
        headers = {"X-OTX-API-KEY": _api_key(), "Accept": "application/json"}

        async with httpx.AsyncClient(timeout=15) as client:
            general = await _fetch_section(
                client, input.indicator_type, input.indicator, "general", headers
            )

        if not general:
            return {"indicator": input.indicator, "found": False}

        pulses = general.get("pulse_info", {})
        result: dict[str, Any] = {
            "indicator": input.indicator,
            "found": True,
            "pulse_count": pulses.get("count", 0),
            "validation": general.get("validation", []),
        }

        # IP-specific fields
        if input.indicator_type == "ip":
            result.update({
                "country_name": general.get("country_name"),
                "country_code": general.get("country_code"),
                "asn": general.get("asn"),
                "city": general.get("city"),
                "reputation": general.get("reputation", 0),
            })

        # Summarise pulse tags and malware families (cap at 10 each)
        tags: list[str] = []
        families: list[str] = []
        for pulse in pulses.get("pulses", [])[:20]:
            tags.extend(pulse.get("tags", []))
            families.extend(pulse.get("malware_families", []))
        result["tags"] = list(dict.fromkeys(tags))[:10]
        result["malware_families"] = list(dict.fromkeys(families))[:10]

        # Recent pulse names
        result["recent_pulses"] = [
            {"name": p.get("name"), "created": p.get("created")}
            for p in pulses.get("pulses", [])[:5]
        ]
        return result


__all__ = ["AlienVaultInput", "AlienVaultTool"]
