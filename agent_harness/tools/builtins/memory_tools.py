from __future__ import annotations

from typing import Any

from agent_harness.domain.models import ToolPermission, ToolSpec
from agent_harness.tools.base import Tool, ToolContext


class MemoryRememberTool(Tool):
    spec = ToolSpec(
        name="memory.remember",
        description="Persist a concise fact or preference in long-term memory.",
        input_schema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "minLength": 1, "maxLength": 4000},
                "kind": {
                    "type": "string",
                    "enum": ["episodic", "semantic", "procedural"],
                    "default": "semantic",
                },
                "importance": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
            },
            "required": ["content"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.WRITE],
        idempotent=True,
    )

    def __init__(self, memory: Any) -> None:
        self.memory = memory

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        memory_id = await self.memory.remember(
            task_id=context.task_id,
            content=arguments["content"],
            kind=arguments.get("kind", "semantic"),
            importance=arguments.get("importance", 0.5),
        )
        return {"memory_id": memory_id, "stored": True}


class MemoryRecallTool(Tool):
    spec = ToolSpec(
        name="memory.recall",
        description="Search long-term memory for facts relevant to a query.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 4000},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        permissions=[ToolPermission.READ],
        idempotent=True,
    )

    def __init__(self, memory: Any) -> None:
        self.memory = memory

    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        records = await self.memory.recall(
            task_id=context.task_id,
            query=arguments["query"],
            limit=arguments.get("limit", 5),
        )
        return {"items": records}

