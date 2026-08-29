from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlparse

import httpx

from agent_harness.domain.errors import HarnessError, ValidationError
from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_title = False
        self.title_parts: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        cleaned = " ".join(data.split())
        if not cleaned:
            return
        if self._in_title:
            self.title_parts.append(cleaned)
        else:
            self.text_parts.append(cleaned)


class BrowserFetchTool(Tool):
    spec = ToolSpec(
        name="browser.fetch",
        description="Fetch a public HTTP(S) page and extract readable text.",
        input_schema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "pattern": "^https?://"},
                "max_chars": {
                    "type": "integer",
                    "minimum": 100,
                    "maximum": 100_000,
                    "default": 12_000,
                },
            },
            "required": ["url"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.NETWORK, ToolPermission.BROWSER],
        idempotent=True,
        timeout_seconds=15,
    )

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        url = arguments["url"]
        await self._validate_public_url(url)
        client = self._client or httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "agent-harness/0.1 (+research bot)"},
        )
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise HarnessError(f"Browser fetch failed: {exc}", details={"retryable": True}) from exc
        finally:
            if self._client is None:
                await client.aclose()

        parser = _TextExtractor()
        parser.feed(response.text)
        text = re.sub(r"\s+", " ", " ".join(parser.text_parts)).strip()
        max_chars = arguments.get("max_chars", 12_000)
        return {
            "url": str(response.url),
            "status_code": response.status_code,
            "title": " ".join(parser.title_parts).strip(),
            "content": text[:max_chars],
            "truncated": len(text) > max_chars,
        }

    @staticmethod
    async def _validate_public_url(url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValidationError("Only public HTTP(S) URLs are allowed")
        if parsed.hostname.lower() in {"localhost", "localhost.localdomain"}:
            raise ValidationError("Localhost URLs are blocked")
        try:
            addresses = await __import__("asyncio").to_thread(
                socket.getaddrinfo,
                parsed.hostname,
                parsed.port or (443 if parsed.scheme == "https" else 80),
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise ValidationError(f"Could not resolve host: {parsed.hostname}") from exc
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ValidationError("Private and reserved network addresses are blocked")

