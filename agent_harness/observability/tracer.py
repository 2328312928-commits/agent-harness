from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from agent_harness.domain.models import RunPhase, TraceEvent, TraceEventType
from agent_harness.storage.repository import HarnessRepository


class EventBus:
    def __init__(self, *, queue_size: int = 500) -> None:
        self.queue_size = queue_size
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._closed_tasks: set[str] = set()
        self._lock = asyncio.Lock()

    async def publish(self, task_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subscribers = list(self._subscribers.get(task_id, set()))
        for queue in subscribers:
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(event)

    async def subscribe(self, task_id: str) -> AsyncIterator[dict[str, Any]]:
        if task_id in self._closed_tasks:
            return
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=self.queue_size)
        async with self._lock:
            self._subscribers[task_id].add(queue)
        try:
            while True:
                item = await queue.get()
                if item.get("event_type") == "_close":
                    break
                yield item
        finally:
            async with self._lock:
                self._subscribers[task_id].discard(queue)
                if not self._subscribers[task_id]:
                    self._subscribers.pop(task_id, None)

    async def close(self, task_id: str) -> None:
        self._closed_tasks.add(task_id)
        await self.publish(task_id, {"event_type": "_close"})


class Tracer:
    def __init__(self, repository: HarnessRepository, bus: EventBus) -> None:
        self.repository = repository
        self.bus = bus

    async def emit(
        self,
        *,
        task_id: str,
        event_type: TraceEventType,
        phase: RunPhase | None = None,
        step: int = 0,
        payload: dict[str, Any] | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
    ) -> TraceEvent:
        event = TraceEvent(
            task_id=task_id,
            event_type=event_type,
            phase=phase,
            step=step,
            timestamp=datetime.now(UTC),
            duration_ms=duration_ms,
            payload=payload or {},
            error=error,
        )
        await self.repository.append_event(event)
        await self.bus.publish(task_id, event.model_dump(mode="json"))
        return event
