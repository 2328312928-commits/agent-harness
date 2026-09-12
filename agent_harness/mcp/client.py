from __future__ import annotations

import asyncio
import json
import os
from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

import httpx

from agent_harness.domain.errors import HarnessError
from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext


class MCPTransport(ABC):
    @abstractmethod
    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        return None

    @abstractmethod
    async def close(self) -> None:
        raise NotImplementedError


class StdioTransport(MCPTransport):
    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = {**os.environ, **(env or {})}
        self.process: asyncio.subprocess.Process | None = None
        self._pending: dict[str, asyncio.Future[dict[str, Any]]] = {}
        self._reader_task: asyncio.Task[None] | None = None
        self._write_lock = asyncio.Lock()

    async def start(self) -> None:
        if self.process is not None:
            return
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=self.env,
        )
        self._reader_task = asyncio.create_task(self._reader_loop())

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
    ) -> dict[str, Any]:
        await self.start()
        request_id = uuid4().hex
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        await self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        try:
            return await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(request_id, None)

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self.start()
        await self._send({"jsonrpc": "2.0", "method": method, "params": params or {}})

    async def _send(self, payload: dict[str, Any]) -> None:
        assert self.process and self.process.stdin
        encoded = (json.dumps(payload, ensure_ascii=False) + "\n").encode()
        async with self._write_lock:
            self.process.stdin.write(encoded)
            await self.process.stdin.drain()

    async def _reader_loop(self) -> None:
        assert self.process and self.process.stdout
        while line := await self.process.stdout.readline():
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            request_id = payload.get("id")
            if request_id is None:
                continue
            future = self._pending.pop(request_id, None)
            if future and not future.done():
                future.set_result(payload)

    async def close(self) -> None:
        if self._reader_task:
            self._reader_task.cancel()
            await asyncio.gather(self._reader_task, return_exceptions=True)
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=3)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        self.process = None


class HTTPTransport(MCPTransport):
    def __init__(self, url: str, headers: dict[str, str] | None = None) -> None:
        self.url = url
        self.headers = headers or {}
        self.client = httpx.AsyncClient(timeout=30, headers=self.headers)

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
    ) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": uuid4().hex,
            "method": method,
            "params": params or {},
        }
        response = await self.client.post(self.url, json=payload, timeout=timeout)
        response.raise_for_status()
        if "text/event-stream" in response.headers.get("content-type", ""):
            for line in response.text.splitlines():
                if line.startswith("data: "):
                    body = json.loads(line.removeprefix("data: "))
                    if body.get("id") == payload["id"]:
                        return body
            raise HarnessError("MCP HTTP response did not contain a matching SSE message")
        return response.json()

    async def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        await self.client.post(
            self.url,
            json={"jsonrpc": "2.0", "method": method, "params": params or {}},
        )

    async def close(self) -> None:
        await self.client.aclose()


class MCPClient:
    def __init__(
        self,
        *,
        name: str,
        transport: MCPTransport,
        client_info: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self.transport = transport
        self.client_info = client_info or {
            "name": "agent-harness",
            "version": "0.2.1",
        }
        self.server_info: dict[str, Any] = {}
        self._initialized = False

    async def initialize(self) -> dict[str, Any]:
        response = self._unwrap(
            await self.transport.request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "roots": {"listChanged": False},
                        "sampling": {},
                    },
                    "clientInfo": self.client_info,
                },
            )
        )
        self.server_info = response
        await self.transport.notify("notifications/initialized")
        self._initialized = True
        return response

    async def list_tools(self) -> list[dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        response = self._unwrap(await self.transport.request("tools/list", {}))
        return list(response.get("tools", []))

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        timeout: float = 60,
    ) -> dict[str, Any]:
        if not self._initialized:
            await self.initialize()
        return self._unwrap(
            await self.transport.request(
                "tools/call",
                {"name": name, "arguments": arguments},
                timeout=timeout,
            )
        )

    async def close(self) -> None:
        await self.transport.close()

    @staticmethod
    def _unwrap(payload: dict[str, Any]) -> dict[str, Any]:
        if "error" in payload:
            error = payload["error"]
            raise HarnessError(
                f"MCP request failed [{error.get('code')}]: {error.get('message')}",
                details={"mcp_error": error},
            )
        result = payload.get("result")
        if not isinstance(result, dict):
            raise HarnessError("MCP response did not include a result object")
        return result


class MCPTool(Tool):
    def __init__(
        self,
        *,
        client: MCPClient,
        definition: dict[str, Any],
        namespace: str,
        permissions: list[ToolPermission],
        idempotent: bool,
        timeout_seconds: float,
    ) -> None:
        self.client = client
        self.remote_name = definition["name"]
        self.namespace = namespace
        self._spec = ToolSpec(
            name=f"{namespace}.{self.remote_name}",
            description=definition.get("description") or f"MCP tool {self.remote_name}",
            input_schema=definition.get("inputSchema")
            or {"type": "object", "properties": {}, "additionalProperties": True},
            permissions=permissions,
            source="mcp",
            idempotent=idempotent,
            timeout_seconds=timeout_seconds,
        )

    @property
    def spec(self) -> ToolSpec:
        return self._spec

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        result = await self.client.call_tool(
            self.remote_name,
            arguments,
            timeout=self.spec.timeout_seconds or 60,
        )
        if result.get("isError"):
            raise HarnessError(self._content_to_text(result.get("content", [])))
        return {
            "mcp_server": self.client.name,
            "content": result.get("content", []),
            "structured_content": result.get("structuredContent"),
            "text": self._content_to_text(result.get("content", [])),
        }

    @staticmethod
    def _content_to_text(content: list[dict[str, Any]]) -> str:
        parts: list[str] = []
        for item in content:
            if item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(json.dumps(item, ensure_ascii=False))
        return "\n".join(parts)


async def load_mcp_tools(configs: list[dict[str, Any]]) -> tuple[list[Tool], list[MCPClient]]:
    tools: list[Tool] = []
    clients: list[MCPClient] = []
    for config in configs:
        if not config.get("enabled", True):
            continue
        namespace = str(config["namespace"])
        permissions = [
            ToolPermission(permission)
            for permission in config.get(
                "permissions",
                ["read", "network"],
            )
        ]
        if config.get("url"):
            transport: MCPTransport = HTTPTransport(
                str(config["url"]),
                headers=config.get("headers"),
            )
        else:
            transport = StdioTransport(
                command=str(config["command"]),
                args=[str(arg) for arg in config.get("args", [])],
                env={str(key): str(value) for key, value in config.get("env", {}).items()},
            )
        client = MCPClient(name=namespace, transport=transport)
        try:
            definitions = await client.list_tools()
            tools.extend(
                MCPTool(
                    client=client,
                    definition=definition,
                    namespace=namespace,
                    permissions=permissions,
                    idempotent=bool(config.get("idempotent", True)),
                    timeout_seconds=float(config.get("timeout_seconds", 60)),
                )
                for definition in definitions
            )
            clients.append(client)
        except Exception:
            await client.close()
            raise
    return tools, clients
