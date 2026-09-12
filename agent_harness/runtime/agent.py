from __future__ import annotations

import asyncio
import contextlib
import json
import re
import time
from datetime import UTC, datetime
from typing import Any

from agent_harness.context.engineer import ContextEngineer
from agent_harness.domain.models import (
    AgentPlan,
    AgentState,
    Message,
    MessageRole,
    PlanStep,
    ProviderResponse,
    RunPhase,
    RuntimeStatus,
    TokenBudgetState,
    ToolCall,
    ToolPermission,
    TraceEventType,
)
from agent_harness.observability.tracer import Tracer
from agent_harness.providers.base import ProviderRequest
from agent_harness.providers.router import ProviderRouter
from agent_harness.runtime.prompts import (
    ACT_SYSTEM_PROMPT,
    PLAN_SYSTEM_PROMPT,
    REFLECT_SYSTEM_PROMPT,
)
from agent_harness.storage.repository import HarnessRepository
from agent_harness.tools.base import ToolContext
from agent_harness.tools.registry import ToolRegistry


def provider_safe_tool_name(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)


class AgentRunner:
    def __init__(
        self,
        *,
        repository: HarnessRepository,
        providers: ProviderRouter,
        tools: ToolRegistry,
        context_engineer: ContextEngineer,
        tracer: Tracer,
        workspace_root: str,
        default_token_budget: int = 32_000,
        default_max_steps: int = 20,
        max_recoveries: int = 3,
    ) -> None:
        self.repository = repository
        self.providers = providers
        self.tools = tools
        self.context_engineer = context_engineer
        self.tracer = tracer
        self.workspace_root = workspace_root
        self.default_token_budget = default_token_budget
        self.default_max_steps = default_max_steps
        self.max_recoveries = max_recoveries

    def create_state(
        self,
        goal: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        max_steps: int | None = None,
        token_budget: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentState:
        selected_provider = self.providers.get(provider)
        state_metadata = metadata or {}
        return AgentState(
            goal=goal,
            provider=selected_provider.name,
            model=model or selected_provider.default_model,
            token_budget=TokenBudgetState(
                limit=token_budget or self.default_token_budget,
            ),
            max_steps=max_steps or self.default_max_steps,
            metadata=state_metadata,
        )

    async def run(self, state: AgentState, cancel_event: asyncio.Event) -> AgentState:
        state.status = RuntimeStatus.RUNNING
        state.updated_at = datetime.now(UTC)
        await self.repository.update_task(state)
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.TASK_STARTED,
            phase=state.phase,
            payload={"goal": state.goal, "provider": state.provider, "model": state.model},
        )

        try:
            if state.plan is None:
                await self._plan(state, cancel_event)
            while state.step_count < state.max_steps:
                if cancel_event.is_set():
                    raise asyncio.CancelledError
                if state.token_budget.remaining <= 0:
                    raise RuntimeError("Token budget exhausted")

                response = await self._act(state, cancel_event)
                state.step_count += 1
                provider_tool_calls = response.tool_calls
                state.messages.append(
                    Message(
                        role=MessageRole.ASSISTANT,
                        content=response.content,
                        reasoning_content=response.reasoning_content,
                        tool_calls=provider_tool_calls,
                    )
                )
                await self._checkpoint(state, "after_act")

                if provider_tool_calls:
                    tool_calls = self._map_provider_tool_calls(provider_tool_calls)
                    await self._observe_and_reflect(state, tool_calls, cancel_event)
                    if state.final_answer:
                        return await self._partial(state)
                    continue

                await self._reflect(state, "No tool call was required.", cancel_event)
                state.final_answer = response.content.strip() or "Task completed."
                if state.metadata.get("unresolved_tool_failures"):
                    state.metadata["partial_reason"] = "unresolved_tool_failure"
                    return await self._partial(state)
                return await self._complete(state)

            raise RuntimeError(f"Maximum agent steps exceeded ({state.max_steps})")
        except asyncio.CancelledError:
            state.status = RuntimeStatus.CANCELLED
            state.error = "Task cancelled"
            await self._checkpoint(state, "cancelled")
            await self.tracer.emit(
                task_id=state.task_id,
                event_type=TraceEventType.TASK_CANCELLED,
                phase=state.phase,
                step=state.step_count,
            )
            return state
        except Exception as exc:  # noqa: BLE001 - runtime boundary persists all failures.
            state.status = RuntimeStatus.FAILED
            state.error = f"{type(exc).__name__}: {exc}"
            state.updated_at = datetime.now(UTC)
            await self._checkpoint(state, "failed")
            await self.tracer.emit(
                task_id=state.task_id,
                event_type=TraceEventType.TASK_FAILED,
                phase=state.phase,
                step=state.step_count,
                error=state.error,
            )
            return state

    async def _plan(self, state: AgentState, cancel_event: asyncio.Event) -> None:
        await self._enter_phase(state, RunPhase.PLAN)
        model_tools, _ = self._model_tools()
        context = await self.context_engineer.build(
            state,
            phase="plan",
            tools=model_tools,
            system_prompt=PLAN_SYSTEM_PROMPT,
        )
        if context.compacted:
            state.token_budget.compaction_count += 1
        response = await self._model_call(
            state,
            phase="plan",
            context_messages=context.messages,
            tools=[],
            cancel_event=cancel_event,
            response_format={"type": "json_object"},
        )
        state.plan = self._parse_plan(response.content, state.goal)
        state.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=response.content,
                reasoning_content=response.reasoning_content,
            )
        )
        await self._checkpoint(state, "after_plan")

    async def _act(self, state: AgentState, cancel_event: asyncio.Event) -> ProviderResponse:
        await self._enter_phase(state, RunPhase.ACT)
        model_tools, tool_name_map = self._model_tools()
        context = await self.context_engineer.build(
            state,
            phase="act",
            tools=model_tools,
            system_prompt=ACT_SYSTEM_PROMPT,
        )
        if context.compacted:
            state.token_budget.compaction_count += 1
        response = await self._model_call(
            state,
            phase="act",
            context_messages=context.messages,
            tools=model_tools,
            cancel_event=cancel_event,
        )
        if not response.content and not response.tool_calls:
            raise RuntimeError("Provider returned neither content nor tool calls")
        return response

    async def _observe_and_reflect(
        self,
        state: AgentState,
        tool_calls: list[ToolCall],
        cancel_event: asyncio.Event,
    ) -> None:
        failures = 0
        for call in tool_calls:
            result = await self._execute_tool(state, call, cancel_event)
            state.observations.append(result)
            self._record_tool_outcome(state, result)
            await self._checkpoint(state, "after_observation")
            await self._reflect(
                state,
                (
                    f"Tool {call.name} succeeded. Output: {str(result.output)[:1200]}"
                    if result.ok
                    else f"Tool {call.name} failed: {result.error}"
                ),
                cancel_event,
            )
            if not result.ok:
                failures += 1
        if failures:
            recovery_count = int(state.metadata.get("recovery_count", 0)) + 1
            state.metadata["recovery_count"] = recovery_count
            if recovery_count > self.max_recoveries:
                state.metadata["recovery_exhausted"] = True
                state.metadata["partial_reason"] = "recovery_limit"
                state.final_answer = (
                    state.reflections[-1]
                    if state.reflections
                    else "Recovery limit reached before the task could be completed."
                )
                return
            await self._replan(state, cancel_event)

    @staticmethod
    def _record_tool_outcome(state: AgentState, result: Any) -> None:
        unresolved = list(state.metadata.get("unresolved_tool_failures", []))
        if result.ok:
            if result.tool_name in unresolved:
                unresolved.remove(result.tool_name)
        else:
            unresolved.append(result.tool_name)
        state.metadata["unresolved_tool_failures"] = unresolved

    async def _execute_tool(
        self,
        state: AgentState,
        call: ToolCall,
        cancel_event: asyncio.Event,
    ) -> Any:
        await self._enter_phase(state, RunPhase.OBSERVE, step=state.step_count)
        permissions = {
            ToolPermission(permission)
            for permission in state.metadata.get(
                "tool_permissions",
                ["read", "write", "network", "execute", "database", "github", "browser"],
            )
        }
        context = ToolContext(
            task_id=state.task_id,
            call_id=call.id,
            permissions=permissions,
            workspace_root=__import__("pathlib").Path(self.workspace_root),
            cancel_event=cancel_event,
            metadata={"tool_name": call.name},
        )
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.TOOL_REQUEST,
            phase=RunPhase.ACT,
            step=state.step_count,
            payload={"call_id": call.id, "tool": call.name, "arguments": call.arguments},
        )
        started = time.perf_counter()
        result = await self.tools.execute(call.name, call.arguments, context)
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.TOOL_RESPONSE,
            phase=RunPhase.OBSERVE,
            step=state.step_count,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "call_id": call.id,
                "tool": call.name,
                "ok": result.ok,
                "attempts": result.attempts,
                "output": self._safe_payload(result.output),
                "error": result.error,
            },
            error=result.error,
        )
        return result

    async def _reflect(
        self,
        state: AgentState,
        observation: str,
        cancel_event: asyncio.Event,
    ) -> None:
        await self._enter_phase(state, RunPhase.REFLECT, step=state.step_count)
        reflection_state = state.model_copy(deep=True)
        reflection_state.messages.append(
            Message(
                role=MessageRole.USER,
                content=(
                    f"Latest observation:\n{observation}\n"
                    "State the next action in one sentence."
                ),
            )
        )
        model_tools, _ = self._model_tools()
        context = await self.context_engineer.build(
            reflection_state,
            phase="reflect",
            tools=model_tools,
            system_prompt=REFLECT_SYSTEM_PROMPT,
        )
        if context.compacted:
            state.token_budget.compaction_count += 1
        response = await self._model_call(
            state,
            phase="reflect",
            context_messages=context.messages,
            tools=[],
            cancel_event=cancel_event,
            max_tokens=300,
        )
        reflection = response.content.strip()
        if reflection:
            state.reflections.append(reflection)
        await self._checkpoint(state, "after_reflection")

    async def _replan(self, state: AgentState, cancel_event: asyncio.Event) -> None:
        await self._enter_phase(state, RunPhase.RECOVERY)
        recovery_goal = (
            f"{state.goal}\n\nThe previous plan failed. Reflection: "
            + (
                state.reflections[-1]
                if state.reflections
                else "Observe the error and avoid repeating it."
            )
        )
        previous_plan = state.plan
        state.plan = None
        recovery_state = state.model_copy(deep=True)
        recovery_state.goal = recovery_goal
        recovery_state.plan = previous_plan
        model_tools, _ = self._model_tools()
        context = await self.context_engineer.build(
            recovery_state,
            phase="plan",
            tools=model_tools,
            system_prompt=PLAN_SYSTEM_PROMPT,
        )
        if context.compacted:
            state.token_budget.compaction_count += 1
        response = await self._model_call(
            state,
            phase="plan",
            context_messages=context.messages,
            tools=[],
            cancel_event=cancel_event,
            response_format={"type": "json_object"},
        )
        state.plan = self._parse_plan(response.content, state.goal)
        if previous_plan:
            state.plan.revision = previous_plan.revision + 1
        state.messages.append(
            Message(
                role=MessageRole.ASSISTANT,
                content=response.content,
                reasoning_content=response.reasoning_content,
                name="replan",
            )
        )
        await self._checkpoint(state, "after_replan")

    async def _model_call(
        self,
        state: AgentState,
        *,
        phase: str,
        context_messages: list[Message],
        tools: list[Any],
        cancel_event: asyncio.Event,
        response_format: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> ProviderResponse:
        provider_name = state.metadata.get("provider_by_phase", {}).get(phase, state.provider)
        model_name = state.metadata.get("model_by_phase", {}).get(
            phase,
            state.model or self.providers.get(provider_name).default_model,
        )
        provider = self.providers.get(provider_name)
        started = time.perf_counter()
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.MODEL_REQUEST,
            phase=RunPhase(phase),
            step=state.step_count,
            payload={
                "provider": provider.name,
                "model": model_name,
                "phase": phase,
                "message_count": len(context_messages),
                "tool_count": len(tools),
                "response_format": response_format,
            },
        )
        task = asyncio.create_task(
            provider.complete(
                ProviderRequest(
                    phase=phase,
                    messages=context_messages,
                    tools=tools,
                    model=model_name,
                    max_tokens=max_tokens,
                    response_format=response_format,
                    metadata={"session_id": state.task_id},
                )
            )
        )
        cancel_task = asyncio.create_task(cancel_event.wait())
        done, _ = await asyncio.wait(
            {task, cancel_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if cancel_task in done and cancel_event.is_set():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise asyncio.CancelledError
        cancel_task.cancel()
        await asyncio.gather(cancel_task, return_exceptions=True)
        response = task.result()

        state.token_budget.prompt_tokens += response.usage.prompt_tokens
        state.token_budget.completion_tokens += response.usage.completion_tokens
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.MODEL_RESPONSE,
            phase=RunPhase(phase),
            step=state.step_count,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "provider": provider.name,
                "model": response.model,
                "content": response.content[:4000],
                "tool_calls": [call.model_dump() for call in response.tool_calls],
                "usage": response.usage.model_dump(),
                "finish_reason": response.finish_reason,
            },
        )
        return response

    def _model_tools(self) -> tuple[list[Any], dict[str, str]]:
        model_tools: list[Any] = []
        name_map: dict[str, str] = {}
        for spec in self.tools.specs():
            safe_name = provider_safe_tool_name(spec.name)
            if safe_name in name_map and name_map[safe_name] != spec.name:
                raise RuntimeError(
                    f"Provider tool name collision: {spec.name} and {name_map[safe_name]}"
                )
            name_map[safe_name] = spec.name
            model_tools.append(spec.model_copy(update={"name": safe_name}))
        return model_tools, name_map

    def _map_provider_tool_calls(self, calls: list[ToolCall]) -> list[ToolCall]:
        _, name_map = self._model_tools()
        return [
            call.model_copy(update={"name": name_map.get(call.name, call.name)})
            for call in calls
        ]

    async def _enter_phase(
        self,
        state: AgentState,
        phase: RunPhase,
        *,
        step: int | None = None,
    ) -> None:
        state.phase = phase
        current_step = state.step_count if step is None else step
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.PHASE_STARTED,
            phase=phase,
            step=current_step,
        )
        self._update_plan_status(state)

    async def _checkpoint(self, state: AgentState, reason: str) -> None:
        state.updated_at = datetime.now(UTC)
        state = await self.repository.save_checkpoint(state, reason=reason)
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.CHECKPOINT_SAVED,
            phase=state.phase,
            step=state.step_count,
            payload={"version": state.checkpoint_version, "reason": reason},
        )

    async def _complete(self, state: AgentState) -> AgentState:
        await self._enter_phase(state, RunPhase.FINALIZE)
        state.status = RuntimeStatus.COMPLETED
        state.completed_at = datetime.now(UTC)
        state.updated_at = state.completed_at
        await self.repository.update_task(state)
        await self._checkpoint(state, "completed")
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.TASK_COMPLETED,
            phase=RunPhase.FINALIZE,
            step=state.step_count,
            payload={
                "final_answer": state.final_answer,
                "total_tokens": state.token_budget.total_tokens,
                "checkpoint_version": state.checkpoint_version,
            },
        )
        await self.tracer.bus.close(state.task_id)
        return state

    async def _partial(self, state: AgentState) -> AgentState:
        await self._enter_phase(state, RunPhase.FINALIZE)
        unresolved = state.metadata.get("unresolved_tool_failures", [])
        if unresolved and not (state.final_answer or "").startswith("任务未完全完成"):
            failures = ", ".join(str(item) for item in unresolved)
            model_answer = state.final_answer or ""
            claims_success = any(
                marker in model_answer.casefold()
                for marker in ("任务已完成", "task completed", "successfully completed")
            )
            acknowledges_failure = (not claims_success) and any(
                marker in model_answer.casefold()
                for marker in ("未完成", "失败", "无法", "不可", "error", "permission")
            )
            state.final_answer = f"任务未完全完成。未解决的工具失败：{failures}。"
            if acknowledges_failure:
                state.final_answer += f"\n\n{model_answer}"
        state.status = RuntimeStatus.PARTIAL
        state.completed_at = datetime.now(UTC)
        state.updated_at = state.completed_at
        await self.repository.update_task(state)
        await self._checkpoint(state, "partial")
        await self.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.TASK_PARTIAL,
            phase=RunPhase.FINALIZE,
            step=state.step_count,
            payload={
                "final_answer": state.final_answer,
                "recovery_count": state.metadata.get("recovery_count", 0),
                "recovery_exhausted": bool(
                    state.metadata.get("recovery_exhausted", False)
                ),
                "partial_reason": state.metadata.get("partial_reason"),
                "unresolved_tool_failures": state.metadata.get(
                    "unresolved_tool_failures",
                    [],
                ),
            },
        )
        await self.tracer.bus.close(state.task_id)
        return state

    @staticmethod
    def _parse_plan(content: str, goal: str) -> AgentPlan:
        candidate = content.strip()
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.DOTALL)
        if fenced:
            candidate = fenced.group(1)
        else:
            object_match = re.search(r"\{.*\}", candidate, re.DOTALL)
            if object_match:
                candidate = object_match.group(0)
        try:
            payload = json.loads(candidate)
            steps = [
                PlanStep(
                    title=str(step.get("title") or f"Step {index + 1}"),
                    description=str(step.get("description") or ""),
                    expected_tools=[str(item) for item in step.get("expected_tools", [])],
                )
                for index, step in enumerate(payload.get("steps", []))
            ]
            return AgentPlan(
                objective=str(payload.get("objective") or goal),
                assumptions=[str(item) for item in payload.get("assumptions", [])],
                steps=steps,
            )
        except (ValueError, TypeError, AttributeError):
            return AgentPlan(
                objective=goal,
                steps=[
                    PlanStep(
                        title="Inspect and act",
                        description="Collect evidence with available tools, then validate results.",
                    ),
                    PlanStep(
                        title="Finalize",
                        description="Return a concise answer grounded in observations.",
                    ),
                ],
            )

    @staticmethod
    def _update_plan_status(state: AgentState) -> None:
        if not state.plan or not state.plan.steps:
            return
        if state.phase == RunPhase.FINALIZE:
            for step in state.plan.steps:
                step.status = "completed"
            return
        target_index = min(state.current_step_index, len(state.plan.steps) - 1)
        for index, step in enumerate(state.plan.steps):
            if index < target_index:
                step.status = "completed"
            elif index == target_index:
                step.status = "in_progress"
            else:
                step.status = "pending"
        if state.phase == RunPhase.REFLECT and state.current_step_index < len(state.plan.steps) - 1:
            state.plan.steps[state.current_step_index].status = "completed"
            state.plan.steps[state.current_step_index].result_summary = (
                state.reflections[-1] if state.reflections else None
            )
            state.current_step_index += 1

    @staticmethod
    def _safe_payload(value: Any) -> Any:
        try:
            json.dumps(value, ensure_ascii=False, default=str)
            return value
        except (TypeError, ValueError):
            return str(value)[:8000]


class RuntimeManager:
    def __init__(self, runner: AgentRunner, repository: HarnessRepository) -> None:
        self.runner = runner
        self.repository = repository
        self.tasks: dict[str, asyncio.Task[AgentState]] = {}
        self.cancel_events: dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def start(
        self,
        goal: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        max_steps: int | None = None,
        token_budget: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentState:
        state = self.runner.create_state(
            goal,
            provider=provider,
            model=model,
            max_steps=max_steps,
            token_budget=token_budget,
            metadata=metadata,
        )
        await self.repository.create_task(state)
        await self.runner.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.TASK_CREATED,
            phase=state.phase,
            payload={"goal": goal},
        )
        self._schedule(state)
        return state

    async def resume(self, task_id: str) -> AgentState:
        current = self.tasks.get(task_id)
        if current and not current.done():
            state = await self.repository.get_task(task_id)
            if state is None:
                raise KeyError(task_id)
            return state
        state = await self.repository.get_task(task_id)
        if state is None:
            raise KeyError(task_id)
        await self.runner.tracer.emit(
            task_id=state.task_id,
            event_type=TraceEventType.RECOVERY_STARTED,
            phase=state.phase,
            step=state.step_count,
            payload={"checkpoint_version": state.checkpoint_version},
        )
        state.status = RuntimeStatus.QUEUED
        state.error = None
        state.completed_at = None
        self._schedule(state)
        return state

    async def cancel(self, task_id: str) -> None:
        self.cancel_events.setdefault(task_id, asyncio.Event()).set()
        task = self.tasks.get(task_id)
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def shutdown(self) -> None:
        for task_id in list(self.tasks):
            await self.cancel(task_id)

    def _schedule(self, state: AgentState) -> None:
        cancel_event = asyncio.Event()
        self.cancel_events[state.task_id] = cancel_event
        task = asyncio.create_task(self._run_and_cleanup(state, cancel_event))
        self.tasks[state.task_id] = task

    async def _run_and_cleanup(
        self,
        state: AgentState,
        cancel_event: asyncio.Event,
    ) -> AgentState:
        try:
            return await self.runner.run(state, cancel_event)
        finally:
            self.tasks.pop(state.task_id, None)
            self.cancel_events.pop(state.task_id, None)
