"""NVDTool: search the NIST National Vulnerability Database for CVEs."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, Field

from aisos.config import get_config
from aisos.tools.base import BaseTool

_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"


class NVDInput(BaseModel):
    cve_id: str | None = Field(
        None,
        description=(
            "Specific CVE ID to fetch (e.g. 'CVE-2021-44228'). "
            "If provided, keyword/severity filters are ignored."
        ),
    )
    keyword: str | None = Field(
        None,
        description=(
            "Free-text keyword search across CVE descriptions "
            "(e.g. 'apache log4j', 'remote code execution')."
        ),
    )
    severity: str | None = Field(
        None,
        description=(
            "Filter by CVSS v3 severity: 'CRITICAL', 'HIGH', 'MEDIUM', or 'LOW'."
        ),
    )
    max_results: int = Field(
        10, ge=1, le=50, description="Maximum number of CVEs to return (1–50)."
    )


def _api_key() -> str:
    return get_config().settings.nvd_api_key  # empty string is fine — unauthenticated still works


def _summarise_cve(cve: dict[str, Any]) -> dict[str, Any]:
    cve_id = cve.get("id", "")
    descriptions = cve.get("descriptions", [])
    desc_en = next(
        (d["value"] for d in descriptions if d.get("lang") == "en"), ""
    )
    metrics = cve.get("metrics", {})

    # Prefer CVSSv3.1, fall back to v3.0 then v2
    score = None
    severity = None
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        bucket = metrics.get(key, [])
        if bucket:
            data = bucket[0].get("cvssData", {})
            score = data.get("baseScore")
            severity = data.get("baseSeverity") or bucket[0].get("baseSeverity")
            break

    published = cve.get("published", "")[:10]
    modified = cve.get("lastModified", "")[:10]
    references = [r.get("url") for r in cve.get("references", [])[:3]]

    return {
        "cve_id": cve_id,
        "description": desc_en[:500],
        "cvss_score": score,
        "severity": severity,
        "published": published,
        "last_modified": modified,
        "references": references,
    }


class NVDTool(BaseTool):
    name = "nvd_cve_lookup"
    description = (
        "Search the NIST NVD for CVE vulnerability records. "
        "Look up a specific CVE by ID (e.g. CVE-2021-44228), search by keyword "
        "(e.g. 'log4j'), or filter by severity (CRITICAL/HIGH/MEDIUM/LOW). "
        "Returns CVSS score, severity, description, and references."
    )
    input_schema = NVDInput
    risk_level = "low"
    required_scope = "read"

    async def run(self, input: NVDInput) -> dict[str, Any]:  # type: ignore[override]
        params: dict[str, Any] = {"resultsPerPage": input.max_results}
        if input.cve_id:
            params["cveId"] = input.cve_id.upper()
        elif input.keyword:
            params["keywordSearch"] = input.keyword
        if input.severity and not input.cve_id:
            params["cvssV3Severity"] = input.severity.upper()

        headers: dict[str, str] = {"Accept": "application/json"}
        key = _api_key()
        if key:
            headers["apiKey"] = key

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(_BASE, headers=headers, params=params)

        if resp.status_code == 404:
            return {"query": params, "total_results": 0, "cves": []}
        resp.raise_for_status()

        body = resp.json()
        vulnerabilities = body.get("vulnerabilities", [])
        cves = [_summarise_cve(v.get("cve", {})) for v in vulnerabilities]
        return {
            "total_results": body.get("totalResults", len(cves)),
            "returned": len(cves),
            "cves": cves,
        }


__all__ = ["NVDInput", "NVDTool"]
