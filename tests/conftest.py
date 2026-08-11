from __future__ import annotations

from pathlib import Path

import pytest

from agent_harness.api.container import AppContainer
from agent_harness.config import Settings


@pytest.fixture
async def container(tmp_path: Path) -> AppContainer:
    workspace = tmp_path / "workspace"
    (workspace / "examples").mkdir(parents=True)
    (workspace / "examples" / "demo.txt").write_text(
        "Agent Harness demo workspace.\n",
        encoding="utf-8",
    )
    settings = Settings(
        app_env="test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'harness.db'}",
        sandbox_backend="local",
        allow_local_code_execution=True,
        workspace_root=workspace,
        tool_default_timeout_seconds=2,
        token_budget=32_000,
    )
    app = AppContainer(settings)
    await app.startup()
    try:
        yield app
    finally:
        await app.shutdown()

