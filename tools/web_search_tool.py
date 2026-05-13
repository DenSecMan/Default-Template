"""WebSearchTool: returns hard-coded mock results (network not allowed)."""

from __future__ import annotations

from pydantic import BaseModel

from aisos.tools.base import BaseTool


class WebSearchInput(BaseModel):
    query: str
    k: int = 3


class WebSearchTool(BaseTool):
    name = "web_search"
    description = "Mock web search. Returns deterministic placeholder hits."
    input_schema = WebSearchInput
    risk_level = "low"
    required_scope = "read"

    _MOCK = [
        {"title": "Mock result 1", "url": "https://example.com/1", "snippet": "Stub."},
        {"title": "Mock result 2", "url": "https://example.com/2", "snippet": "Stub."},
        {"title": "Mock result 3", "url": "https://example.com/3", "snippet": "Stub."},
        {"title": "Mock result 4", "url": "https://example.com/4", "snippet": "Stub."},
        {"title": "Mock result 5", "url": "https://example.com/5", "snippet": "Stub."},
    ]

    async def run(self, input: WebSearchInput) -> dict[str, object]:  # type: ignore[override]
        return {
            "query": input.query,
            "results": [{**hit, "query": input.query} for hit in self._MOCK[: input.k]],
        }


__all__ = ["WebSearchInput", "WebSearchTool"]
