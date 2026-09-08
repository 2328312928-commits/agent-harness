from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select

from agent_harness.domain.models import (
    AgentState,
    EvalRunSummary,
    RuntimeStatus,
    TaskSummary,
    TraceEvent,
)
from agent_harness.storage.database import Database
from agent_harness.storage.models import (
    CheckpointRecord,
    EvalRunRecord,
    EventRecord,
    MemoryRecord,
    TaskRecord,
)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


class HarnessRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    async def create_task(self, state: AgentState) -> AgentState:
        async with self.database.session_factory() as session:
            record = TaskRecord(
                id=state.task_id,
                goal=state.goal,
                status=state.status.value,
                phase=state.phase.value,
                provider=state.provider,
                model=state.model,
                state=state.model_dump(mode="json"),
                created_at=state.created_at,
                updated_at=state.updated_at,
                completed_at=state.completed_at,
            )
            session.add(record)
            await session.commit()
        return state

    async def update_task(self, state: AgentState) -> AgentState:
        state.updated_at = datetime.now(UTC)
        async with self.database.session_factory() as session:
            record = await session.get(TaskRecord, state.task_id)
            if record is None:
                record = TaskRecord(
                    id=state.task_id,
                    goal=state.goal,
                    status=state.status.value,
                    phase=state.phase.value,
                    provider=state.provider,
                    model=state.model,
                    state=state.model_dump(mode="json"),
                    created_at=state.created_at,
                    updated_at=state.updated_at,
                    completed_at=state.completed_at,
                )
                session.add(record)
            else:
                record.goal = state.goal
                record.status = state.status.value
                record.phase = state.phase.value
                record.provider = state.provider
                record.model = state.model
                record.state = state.model_dump(mode="json")
                record.updated_at = state.updated_at
                record.completed_at = state.completed_at
            await session.commit()
        return state

    async def get_task(self, task_id: str) -> AgentState | None:
        async with self.database.session_factory() as session:
            record = await session.get(TaskRecord, task_id)
            if record is None:
                return None
            return AgentState.model_validate(record.state)

    async def list_tasks(self, *, limit: int = 100, offset: int = 0) -> list[TaskSummary]:
        async with self.database.session_factory() as session:
            records = (
                await session.scalars(
                    select(TaskRecord)
                    .order_by(desc(TaskRecord.updated_at))
                    .offset(offset)
                    .limit(limit)
                )
            ).all()
        summaries: list[TaskSummary] = []
        for record in records:
            state = AgentState.model_validate(record.state)
            duration_ms = None
            if state.completed_at:
                duration_ms = (state.completed_at - state.created_at).total_seconds() * 1000
            summaries.append(
                TaskSummary(
                    task_id=state.task_id,
                    goal=state.goal,
                    status=state.status,
                    phase=state.phase,
                    provider=state.provider,
                    model=state.model,
                    step_count=state.step_count,
                    total_tokens=state.token_budget.total_tokens,
                    created_at=state.created_at,
                    updated_at=state.updated_at,
                    completed_at=state.completed_at,
                    duration_ms=duration_ms,
                )
            )
        return summaries

    async def append_event(self, event: TraceEvent) -> None:
        async with self.database.session_factory() as session:
            session.add(
                EventRecord(
                    id=event.id,
                    task_id=event.task_id,
                    event_type=event.event_type.value,
                    phase=event.phase.value if event.phase else None,
                    step=event.step,
                    timestamp=event.timestamp,
                    duration_ms=event.duration_ms,
                    payload=event.payload,
                    error=event.error,
                )
            )
            await session.commit()

    async def list_events(
        self,
        task_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        async with self.database.session_factory() as session:
            records = (
                await session.scalars(
                    select(EventRecord)
                    .where(
                        EventRecord.task_id == task_id,
                        EventRecord.sequence > after_sequence,
                    )
                    .order_by(EventRecord.sequence)
                    .limit(limit)
                )
            ).all()
        return [
            {
                "sequence": record.sequence,
                "id": record.id,
                "task_id": record.task_id,
                "event_type": record.event_type,
                "phase": record.phase,
                "step": record.step,
                "timestamp": record.timestamp,
                "duration_ms": record.duration_ms,
                "payload": record.payload,
                "error": record.error,
            }
            for record in records
        ]

    async def save_checkpoint(
        self,
        state: AgentState,
        *,
        reason: str,
    ) -> AgentState:
        state.checkpoint_version += 1
        checkpoint = CheckpointRecord(
            id=f"ckpt_{uuid4().hex[:16]}",
            task_id=state.task_id,
            version=state.checkpoint_version,
            phase=state.phase.value,
            reason=reason,
            state=state.model_dump(mode="json"),
            created_at=datetime.now(UTC),
        )
        async with self.database.session_factory() as session:
            session.add(checkpoint)
            await session.commit()
        return await self.update_task(state)

    async def latest_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        async with self.database.session_factory() as session:
            record = await session.scalar(
                select(CheckpointRecord)
                .where(CheckpointRecord.task_id == task_id)
                .order_by(desc(CheckpointRecord.version))
                .limit(1)
            )
        if record is None:
            return None
        return {
            "id": record.id,
            "task_id": record.task_id,
            "version": record.version,
            "phase": record.phase,
            "reason": record.reason,
            "state": record.state,
            "created_at": record.created_at,
        }

    async def remember(
        self,
        *,
        task_id: str | None,
        content: str,
        kind: str,
        importance: float,
    ) -> str:
        memory_id = f"mem_{uuid4().hex[:16]}"
        record = MemoryRecord(
            id=memory_id,
            task_id=task_id,
            kind=kind,
            content=content,
            importance=importance,
            terms=self._terms(content),
            access_count=0,
            created_at=datetime.now(UTC),
        )
        async with self.database.session_factory() as session:
            session.add(record)
            await session.commit()
        return memory_id

    async def recall(
        self,
        *,
        task_id: str | None,
        query: str,
        limit: int,
    ) -> list[dict[str, Any]]:
        query_terms = Counter(self._terms(query))
        async with self.database.session_factory() as session:
            records = (
                await session.scalars(
                    select(MemoryRecord)
                    .order_by(desc(MemoryRecord.importance), desc(MemoryRecord.created_at))
                    .limit(500)
                )
            ).all()
            scored: list[tuple[float, MemoryRecord]] = []
            for record in records:
                record_terms = Counter(record.terms)
                overlap = sum((query_terms & record_terms).values())
                same_task = 0.15 if task_id and record.task_id == task_id else 0
                score = overlap + record.importance * 0.5 + same_task
                if score > 0:
                    scored.append((score, record))
            selected = [
                record
                for _, record in sorted(scored, key=lambda item: item[0], reverse=True)[:limit]
            ]
            for record in selected:
                record.access_count += 1
                record.last_accessed_at = datetime.now(UTC)
            await session.commit()
        return [
            {
                "id": record.id,
                "kind": record.kind,
                "content": record.content,
                "importance": record.importance,
            }
            for record in selected
        ]

    async def save_eval_run(self, summary: EvalRunSummary) -> None:
        async with self.database.session_factory() as session:
            record = EvalRunRecord(
                id=summary.run_id,
                provider=summary.provider,
                model=summary.model,
                strategy=summary.strategy,
                summary=summary.model_dump(mode="json"),
                created_at=summary.started_at,
                completed_at=summary.completed_at,
            )
            session.add(record)
            await session.commit()

    async def list_eval_runs(self, *, limit: int = 30) -> list[EvalRunSummary]:
        async with self.database.session_factory() as session:
            records = (
                await session.scalars(
                    select(EvalRunRecord).order_by(desc(EvalRunRecord.created_at)).limit(limit)
                )
            ).all()
        return [EvalRunSummary.model_validate(record.summary) for record in records]

    async def metrics(self) -> dict[str, Any]:
        async with self.database.session_factory() as session:
            total_tasks = await session.scalar(select(func.count(TaskRecord.id))) or 0
            status_rows = (
                await session.execute(
                    select(TaskRecord.status, func.count(TaskRecord.id)).group_by(TaskRecord.status)
                )
            ).all()
            checkpoint_count = await session.scalar(select(func.count(CheckpointRecord.id))) or 0
            memory_count = await session.scalar(select(func.count(MemoryRecord.id))) or 0
            events = (
                await session.execute(
                    select(EventRecord.event_type, func.count(EventRecord.id)).group_by(
                        EventRecord.event_type
                    )
                )
            ).all()
        statuses = {status: count for status, count in status_rows}
        completed = statuses.get(RuntimeStatus.COMPLETED.value, 0)
        partial = statuses.get(RuntimeStatus.PARTIAL.value, 0)
        failed = statuses.get(RuntimeStatus.FAILED.value, 0)
        denominator = completed + partial + failed
        return {
            "tasks": {
                "total": total_tasks,
                "by_status": statuses,
                "completion_rate": completed / denominator if denominator else 0,
            },
            "checkpoints": checkpoint_count,
            "memories": memory_count,
            "events": {event_type: count for event_type, count in events},
        }

    @staticmethod
    def _terms(content: str) -> list[str]:
        latin = re.findall(r"[a-zA-Z0-9_]{2,}", content.lower())
        chinese = re.findall(r"[\u4e00-\u9fff]{2,}", content)
        return sorted(set(latin + chinese))[:128]
