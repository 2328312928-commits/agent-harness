from __future__ import annotations

import sys
from pathlib import Path

from agent_harness.mcp.client import MCPClient, StdioTransport


async def test_mcp_stdio_discovery_and_call(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "demo.txt").write_text("mcp works", encoding="utf-8")
    client = MCPClient(
        name="demo",
        transport=StdioTransport(
            command=sys.executable,
            args=["-m", "agent_harness.mcp.demo_server"],
            env={"MCP_WORKSPACE_ROOT": str(workspace)},
        ),
    )
    try:
        server = await client.initialize()
        tools = await client.list_tools()
        assert server["serverInfo"]["name"] == "agent-harness-demo"
        assert {tool["name"] for tool in tools} == {
            "fs_read",
            "github_search_repositories",
            "database_query",
            "browser_fetch",
            "sandbox_run_python",
        }
        result = await client.call_tool("fs_read", {"path": "demo.txt"})
        assert result["structuredContent"]["content"] == "mcp works"
    finally:
        await client.close()

