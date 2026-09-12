from __future__ import annotations

import json
import os
import sqlite3
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import httpx


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and (cleaned := " ".join(data.split())):
            self.parts.append(cleaned)


def _safe_workspace_path(path: str) -> Path:
    root = Path(os.getenv("MCP_WORKSPACE_ROOT", "./workspace")).resolve()
    target = (root / path).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Path escapes MCP workspace root")
    return target


def fs_read(arguments: dict[str, Any]) -> Any:
    path = _safe_workspace_path(arguments["path"])
    return {"path": str(path), "content": path.read_text(encoding="utf-8")}


def github_search_repositories(arguments: dict[str, Any]) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "agent-harness-mcp-demo",
    }
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    response = httpx.get(
        "https://api.github.com/search/repositories",
        params={"q": arguments["query"], "per_page": min(int(arguments.get("limit", 5)), 10)},
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    return {
        "items": [
            {
                "full_name": item["full_name"],
                "url": item["html_url"],
                "stars": item["stargazers_count"],
            }
            for item in response.json().get("items", [])
        ]
    }


def database_query(arguments: dict[str, Any]) -> Any:
    query = str(arguments["query"]).strip()
    if not query.lower().startswith(("select", "with", "pragma", "explain")):
        raise ValueError("Only read-only queries are allowed")
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE metrics(name TEXT, value REAL)")
    connection.executemany(
        "INSERT INTO metrics VALUES (?, ?)",
        [("task_success_rate", 0.91), ("p95_latency_ms", 1840), ("tools", 5)],
    )
    cursor = connection.execute(query)
    columns = [column[0] for column in cursor.description or []]
    rows = [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]
    connection.close()
    return {"columns": columns, "rows": rows}


def browser_fetch(arguments: dict[str, Any]) -> Any:
    response = httpx.get(
        arguments["url"],
        timeout=15,
        follow_redirects=True,
        headers={"User-Agent": "agent-harness-mcp-demo"},
    )
    response.raise_for_status()
    parser = _TextExtractor()
    parser.feed(response.text)
    text = " ".join(parser.parts)
    return {"url": str(response.url), "status_code": response.status_code, "text": text[:12000]}


def sandbox_run_python(arguments: dict[str, Any]) -> Any:
    # This MCP server is a protocol demo. Production deployments should route this
    # tool to the containerized Sandbox service instead of evaluating code in-process.
    expression = str(arguments["code"]).strip()
    if not expression.startswith("print(") or not expression.endswith(")"):
        raise ValueError("Demo MCP sandbox only accepts a single print(...) expression")
    inner = expression[6:-1]
    if not all(character in "0123456789+-*/().% " for character in inner):
        raise ValueError("Unsupported expression")
    return {"stdout": str(eval(inner, {"__builtins__": {}}, {})) + "\n", "exit_code": 0}


TOOLS: dict[str, dict[str, Any]] = {
    "fs_read": {
        "description": "Read a UTF-8 file inside MCP_WORKSPACE_ROOT.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "handler": fs_read,
    },
    "github_search_repositories": {
        "description": "Search repositories through the public GitHub API.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        "handler": github_search_repositories,
    },
    "database_query": {
        "description": "Run read-only SQL against a seeded demo SQLite database.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "handler": database_query,
    },
    "browser_fetch": {
        "description": "Fetch and normalize a public web page.",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string", "pattern": "^https?://"}},
            "required": ["url"],
            "additionalProperties": False,
        },
        "handler": browser_fetch,
    },
    "sandbox_run_python": {
        "description": "Evaluate a constrained Python print expression in the protocol demo.",
        "inputSchema": {
            "type": "object",
            "properties": {"code": {"type": "string"}},
            "required": ["code"],
            "additionalProperties": False,
        },
        "handler": sandbox_run_python,
    },
}


def _response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(payload: dict[str, Any]) -> dict[str, Any] | None:
    method = payload.get("method")
    request_id = payload.get("id")
    if method == "initialize":
        return _response(
            request_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": "agent-harness-demo", "version": "0.2.1"},
            },
        )
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(
            request_id,
            {
                "tools": [
                    {
                        "name": name,
                        "description": definition["description"],
                        "inputSchema": definition["inputSchema"],
                    }
                    for name, definition in TOOLS.items()
                ]
            },
        )
    if method == "tools/call":
        params = payload.get("params", {})
        name = params.get("name")
        definition = TOOLS.get(name)
        if not definition:
            return _error(request_id, -32602, f"Unknown tool: {name}")
        try:
            output = definition["handler"](params.get("arguments", {}))
            return _response(
                request_id,
                {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(output, ensure_ascii=False, default=str),
                        }
                    ],
                    "structuredContent": output,
                    "isError": False,
                },
            )
        except Exception as exc:  # noqa: BLE001 - convert tool errors to MCP results.
            return _response(
                request_id,
                {
                    "content": [{"type": "text", "text": f"{type(exc).__name__}: {exc}"}],
                    "isError": True,
                },
            )
    return _error(request_id, -32601, f"Method not found: {method}")


def main() -> None:
    for line in sys.stdin:
        try:
            payload = json.loads(line)
            response = handle(payload)
        except Exception as exc:  # noqa: BLE001
            response = _error(None, -32700, f"Parse error: {exc}")
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()

