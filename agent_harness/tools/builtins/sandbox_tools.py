from __future__ import annotations

from typing import Any

from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.sandbox.base import Sandbox
from agent_harness.tools.base import Tool, ToolContext


class SandboxPythonTool(Tool):
    spec = ToolSpec(
        name="sandbox.run_python",
        description="Execute short Python code in an isolated, network-disabled container.",
        input_schema={
            "type": "object",
            "properties": {
                "code": {"type": "string", "minLength": 1, "maxLength": 50_000},
                "timeout_seconds": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 60,
                },
            },
            "required": ["code"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.EXECUTE],
        idempotent=True,
        timeout_seconds=70,
    )

    def __init__(self, sandbox: Sandbox) -> None:
        self.sandbox = sandbox

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        result = await self.sandbox.run_python(
            arguments["code"],
            timeout_seconds=arguments.get("timeout_seconds"),
        )
        return result.model_dump()

