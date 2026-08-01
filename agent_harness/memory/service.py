from __future__ import annotations

from typing import Any

from agent_harness.storage.repository import HarnessRepository


class TokenEstimator:
    """Conservative token estimate without requiring a tokenizer per provider."""

    @staticmethod
    def estimate_text(text: str) -> int:
        if not text:
            return 0
        latin_chars = sum(1 for character in text if ord(character) < 128)
        non_latin_chars = len(text) - latin_chars
        return max(1, latin_chars // 4 + int(non_latin_chars * 1.15))

    @classmethod
    def estimate_messages(cls, messages: list[Any]) -> int:
        total = 0
        for message in messages:
            total += cls.estimate_text(getattr(message, "content", "")) + 8
            for tool_call in getattr(message, "tool_calls", []):
                total += cls.estimate_text(tool_call.name) + cls.estimate_text(
                    str(tool_call.arguments)
                )
        return total


class MemoryService:
    def __init__(self, repository: HarnessRepository, *, enabled: bool = True) -> None:
        self.repository = repository
        self.enabled = enabled

    async def remember(
        self,
        *,
        task_id: str | None,
        content: str,
        kind: str = "semantic",
        importance: float = 0.5,
    ) -> str:
        return await self.repository.remember(
            task_id=task_id,
            content=content,
            kind=kind,
            importance=importance,
        )

    async def recall(
        self,
        *,
        task_id: str | None,
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        return await self.repository.recall(task_id=task_id, query=query, limit=limit)

