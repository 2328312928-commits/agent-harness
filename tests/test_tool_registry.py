from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext
from agent_harness.tools.registry import ToolRegistry


class EchoTool(Tool):
    spec = ToolSpec(
        name="test.echo",
        description="Echo a value.",
        input_schema={
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.READ],
        idempotent=True,
    )

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        return {"value": arguments["value"]}


class FlakyTool(EchoTool):
    spec = EchoTool.spec.model_copy(
        update={"name": "test.flaky", "idempotent": True},
    )

    def __init__(self) -> None:
        self.attempts = 0

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        self.attempts += 1
        if self.attempts == 1:
            from agent_harness.domain.errors import HarnessError

            error = HarnessError("temporary failure")
            error.retryable = True
            raise error
        return {"value": arguments["value"]}


class SlowTool(EchoTool):
    spec = EchoTool.spec.model_copy(
        update={"name": "test.slow", "idempotent": False, "timeout_seconds": 0.05},
    )

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        await asyncio.sleep(0.5)
        return {"value": arguments["value"]}


def tool_context() -> ToolContext:
    return ToolContext(
        task_id="task",
        call_id="call",
        permissions={ToolPermission.READ},
        workspace_root=Path.cwd(),
    )


async def test_registry_validates_arguments() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    result = await registry.execute("test.echo", {}, tool_context())
    assert not result.ok
    assert result.error_type == "validation_error"


async def test_registry_retries_idempotent_tool() -> None:
    registry = ToolRegistry(default_max_retries=2)
    registry.register(FlakyTool())
    result = await registry.execute("test.flaky", {"value": "ok"}, tool_context())
    assert result.ok
    assert result.attempts == 2


async def test_registry_times_out() -> None:
    registry = ToolRegistry(default_max_retries=0)
    registry.register(SlowTool())
    result = await registry.execute("test.slow", {"value": "ok"}, tool_context())
    assert not result.ok
    assert result.error_type == "tool_timeout"


async def test_registry_enforces_permission() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    context = tool_context()
    context.permissions = set()
    result = await registry.execute("test.echo", {"value": "ok"}, context)
    assert not result.ok
    assert result.error_type == "tool_permission_denied"
