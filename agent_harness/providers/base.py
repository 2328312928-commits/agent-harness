from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from agent_harness.domain.models import Message, ProviderResponse, ToolSpec


class ProviderRequest(BaseModel):
    phase: str
    messages: list[Message]
    tools: list[ToolSpec] = Field(default_factory=list)
    model: str | None = None
    max_tokens: int | None = None
    temperature: float = 0.1
    response_format: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LLMProvider(ABC):
    name: str
    default_model: str

    @abstractmethod
    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        raise NotImplementedError

    async def health(self) -> dict[str, Any]:
        return {"provider": self.name, "model": self.default_model, "ok": True}

    async def close(self) -> None:
        return None
