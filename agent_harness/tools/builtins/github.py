from __future__ import annotations

from typing import Any

import httpx

from agent_harness.domain.errors import HarnessError
from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext


class GitHubSearchRepositoriesTool(Tool):
    spec = ToolSpec(
        name="github.search_repositories",
        description="Search public GitHub repositories using the GitHub REST API.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 256},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.NETWORK, ToolPermission.GITHUB],
        idempotent=True,
        timeout_seconds=20,
    )

    def __init__(self, token: str = "", client: httpx.AsyncClient | None = None) -> None:
        self.token = token
        self._client = client

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "agent-harness",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        client = self._client or httpx.AsyncClient(timeout=15)
        try:
            response = await client.get(
                "https://api.github.com/search/repositories",
                params={"q": arguments["query"], "per_page": arguments.get("limit", 5)},
                headers=headers,
            )
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPError as exc:
            raise HarnessError(
                f"GitHub API request failed: {exc}",
                details={"retryable": True},
            ) from exc
        finally:
            if self._client is None:
                await client.aclose()

        return {
            "total_count": payload.get("total_count", 0),
            "items": [
                {
                    "full_name": item.get("full_name"),
                    "html_url": item.get("html_url"),
                    "description": item.get("description"),
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language"),
                    "updated_at": item.get("updated_at"),
                }
                for item in payload.get("items", [])
            ],
        }
