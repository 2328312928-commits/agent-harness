from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_harness.domain.models import ToolPermission, ToolSpec


@dataclass(slots=True)
class ToolContext:
    task_id: str
    call_id: str
    permissions: set[ToolPermission]
    workspace_root: Path
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    metadata: dict[str, Any] = field(default_factory=dict)


class Tool(ABC):
    @property
    @abstractmethod
    def spec(self) -> ToolSpec:
        raise NotImplementedError

    @abstractmethod
    async def run(self, arguments: dict[str, Any], context: ToolContext) -> Any:
        raise NotImplementedError

