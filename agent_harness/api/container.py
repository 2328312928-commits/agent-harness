from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_harness.api.security import SlidingWindowRateLimiter
from agent_harness.config import Settings
from agent_harness.context.engineer import ContextEngineer
from agent_harness.evals.runner import EvalRunner
from agent_harness.mcp.client import MCPClient, load_mcp_tools
from agent_harness.memory.service import MemoryService
from agent_harness.observability.tracer import EventBus, Tracer
from agent_harness.providers.router import ProviderRouter
from agent_harness.runtime.agent import AgentRunner, RuntimeManager
from agent_harness.sandbox.docker import DockerSandbox
from agent_harness.sandbox.local import LocalProcessSandbox
from agent_harness.storage.database import Database
from agent_harness.storage.repository import HarnessRepository
from agent_harness.tools.builtins import (
    BrowserFetchTool,
    DatabaseQueryTool,
    FileReadTool,
    FileWriteTool,
    GitHubSearchRepositoriesTool,
    ListDirectoryTool,
    MemoryRecallTool,
    MemoryRememberTool,
    SandboxPythonTool,
)
from agent_harness.tools.registry import ToolRegistry


@dataclass
class AppContainer:
    settings: Settings
    database: Database = field(init=False)
    repository: HarnessRepository = field(init=False)
    memory: MemoryService = field(init=False)
    providers: ProviderRouter = field(init=False)
    tools: ToolRegistry = field(init=False)
    tracer: Tracer = field(init=False)
    runtime: RuntimeManager = field(init=False)
    evals: EvalRunner = field(init=False)
    mcp_clients: list[MCPClient] = field(default_factory=list)
    rate_limiter: SlidingWindowRateLimiter = field(init=False)

    async def startup(self) -> None:
        if (
            self.settings.app_env == "production"
            and not self.settings.public_demo_mode
            and not self.settings.api_auth_token
        ):
            raise RuntimeError(
                "Production write API requires API_AUTH_TOKEN or PUBLIC_DEMO_MODE=true"
            )
        examples_dir = self.settings.resolved_workspace_root / "examples"
        examples_dir.mkdir(parents=True, exist_ok=True)
        demo_file = examples_dir / "demo.txt"
        if not demo_file.exists():
            demo_file.write_text(
                "Agent Harness demo workspace.\n",
                encoding="utf-8",
            )
        self.rate_limiter = SlidingWindowRateLimiter(
            limit=self.settings.public_demo_rate_limit_per_minute
        )
        self.database = Database(self.settings.database_url)
        await self.database.initialize()
        self.repository = HarnessRepository(self.database)
        self.memory = MemoryService(
            self.repository,
            enabled=self.settings.long_term_memory_enabled,
        )
        self.providers = ProviderRouter(self.settings)
        bus = EventBus()
        self.tracer = Tracer(self.repository, bus)
        self.tools = ToolRegistry(
            default_timeout_seconds=self.settings.tool_default_timeout_seconds,
            default_max_retries=self.settings.tool_max_retries,
        )
        await self._register_tools()
        context_engineer = ContextEngineer(
            token_budget=self.settings.token_budget,
            summary_trigger_tokens=self.settings.summary_trigger_tokens,
            memory=self.memory,
        )
        runner = AgentRunner(
            repository=self.repository,
            providers=self.providers,
            tools=self.tools,
            context_engineer=context_engineer,
            tracer=self.tracer,
            workspace_root=str(self.settings.resolved_workspace_root),
            default_token_budget=self.settings.token_budget,
        )
        self.runtime = RuntimeManager(runner, self.repository)
        self.evals = EvalRunner(
            runner=runner,
            repository=self.repository,
            dataset_path=Path("evals/dataset/seed_tasks.jsonl"),
        )

    async def shutdown(self) -> None:
        if hasattr(self, "runtime"):
            await self.runtime.shutdown()
        for client in self.mcp_clients:
            await client.close()
        if hasattr(self, "providers"):
            await self.providers.close()
        if hasattr(self, "database"):
            await self.database.close()

    async def _register_tools(self) -> None:
        if (
            self.settings.sandbox_backend == "local"
            and not self.settings.allow_local_code_execution
        ):
            raise RuntimeError(
                "Local code execution is disabled. Set ALLOW_LOCAL_CODE_EXECUTION=true "
                "only for development, or use SANDBOX_BACKEND=docker."
            )
        sandbox = (
            DockerSandbox(
                image=self.settings.sandbox_image,
                memory_limit=self.settings.sandbox_memory_limit,
                cpu_limit=self.settings.sandbox_cpu_limit,
                default_timeout_seconds=self.settings.sandbox_timeout_seconds,
                network_disabled=self.settings.sandbox_network_disabled,
            )
            if self.settings.sandbox_backend == "docker"
            else LocalProcessSandbox(default_timeout_seconds=self.settings.sandbox_timeout_seconds)
        )
        builtins = [
            FileReadTool(),
            FileWriteTool(),
            ListDirectoryTool(),
            GitHubSearchRepositoriesTool(self.settings.github_token),
            BrowserFetchTool(),
            DatabaseQueryTool(
                self.settings.database_readonly_url or self.settings.database_url
            ),
            SandboxPythonTool(sandbox),
            MemoryRememberTool(self.memory),
            MemoryRecallTool(self.memory),
        ]
        for tool in builtins:
            self.tools.register(tool)

        configs = self.settings.mcp_servers_json or [self._demo_mcp_config()]
        mcp_tools, self.mcp_clients = await load_mcp_tools(configs)
        for tool in mcp_tools:
            self.tools.register(tool)

    def _demo_mcp_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "namespace": "demo",
            "command": sys.executable,
            "args": ["-m", "agent_harness.mcp.demo_server"],
            "env": {"MCP_WORKSPACE_ROOT": str(self.settings.resolved_workspace_root)},
            "permissions": ["read", "network", "execute", "database", "github", "browser"],
            "idempotent": False,
            "timeout_seconds": 20,
        }
