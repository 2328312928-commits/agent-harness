from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from agent_harness.domain.errors import (
    HarnessError,
    ToolCancelledError,
    ToolNotFoundError,
    ToolPermissionError,
    ToolTimeoutError,
    ValidationError,
)
from agent_harness.domain.models import ToolPermission, ToolResult, ToolSpec
from agent_harness.tools.base import Tool, ToolContext

ToolEventHandler = Callable[[str, ToolContext, dict[str, Any]], Awaitable[None]]


class ToolRegistry:
    def __init__(
        self,
        *,
        default_timeout_seconds: float = 30,
        default_max_retries: int = 2,
        event_handler: ToolEventHandler | None = None,
    ) -> None:
        self.default_timeout_seconds = default_timeout_seconds
        self.default_max_retries = default_max_retries
        self.event_handler = event_handler
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool, *, replace: bool = False) -> None:
        name = tool.spec.name
        if name in self._tools and not replace:
            raise ValidationError(f"Tool already registered: {name}")
        self._tools[name] = tool

    def unregister(self, name: str) -> None:
        self._tools.pop(name, None)

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(f"Unknown tool: {name}") from exc

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]

    async def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        context: ToolContext,
    ) -> ToolResult:
        started = time.perf_counter()
        try:
            tool = self.get(name)
            self._validate(tool.spec, arguments)
            self._authorize(tool.spec, context.permissions)
        except HarnessError as exc:
            return ToolResult(
                call_id=context.call_id,
                tool_name=name,
                ok=False,
                error=exc.message,
                error_type=exc.code,
                latency_ms=(time.perf_counter() - started) * 1000,
                retryable=exc.retryable,
            )

        max_retries = (
            tool.spec.max_retries
            if tool.spec.max_retries is not None
            else self.default_max_retries
        )
        timeout_seconds = tool.spec.timeout_seconds or self.default_timeout_seconds
        attempts = 0
        last_error: HarnessError | None = None

        while attempts <= max_retries:
            attempts += 1
            if context.cancel_event.is_set():
                return self._failure(
                    context,
                    ToolCancelledError("Tool execution was cancelled"),
                    started,
                    attempts,
                )
            try:
                await self._emit("tool.started", context, {"tool": name, "attempt": attempts})
                output = await self._run_with_timeout(tool, arguments, context, timeout_seconds)
                return ToolResult(
                    call_id=context.call_id,
                    tool_name=name,
                    ok=True,
                    output=output,
                    latency_ms=(time.perf_counter() - started) * 1000,
                    attempts=attempts,
                    metadata={"source": tool.spec.source},
                )
            except asyncio.CancelledError:
                raise
            except HarnessError as exc:
                last_error = exc
            except Exception as exc:  # noqa: BLE001 - tool implementations are untrusted.
                last_error = HarnessError(f"{type(exc).__name__}: {exc}")

            retryable = bool(last_error.retryable and tool.spec.idempotent)
            if not retryable or attempts > max_retries:
                break
            await self._emit(
                "tool.retry",
                context,
                {
                    "tool": name,
                    "attempt": attempts,
                    "error": last_error.message,
                    "error_type": last_error.code,
                },
            )

        assert last_error is not None
        return self._failure(context, last_error, started, attempts)

    async def _run_with_timeout(
        self,
        tool: Tool,
        arguments: dict[str, Any],
        context: ToolContext,
        timeout_seconds: float,
    ) -> Any:
        task = asyncio.create_task(tool.run(arguments, context))
        cancel_task = asyncio.create_task(context.cancel_event.wait())
        try:
            done, _ = await asyncio.wait(
                {task, cancel_task},
                timeout=timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not done:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise ToolTimeoutError(
                    f"Tool timed out after {timeout_seconds:.1f}s",
                    details={"timeout_seconds": timeout_seconds},
                )
            if cancel_task in done and context.cancel_event.is_set():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
                raise ToolCancelledError("Tool execution was cancelled")
            return task.result()
        finally:
            cancel_task.cancel()
            await asyncio.gather(cancel_task, return_exceptions=True)

    @staticmethod
    def _validate(spec: ToolSpec, arguments: dict[str, Any]) -> None:
        validator = Draft202012Validator(spec.input_schema)
        errors = sorted(validator.iter_errors(arguments), key=lambda item: list(item.path))
        if errors:
            details = [ToolRegistry._format_validation_error(error) for error in errors]
            raise ValidationError(
                f"Invalid arguments for {spec.name}",
                details={"errors": details},
            )

    @staticmethod
    def _format_validation_error(error: JsonSchemaValidationError) -> dict[str, Any]:
        path = ".".join(str(part) for part in error.absolute_path) or "$"
        return {"path": path, "message": error.message}

    @staticmethod
    def _authorize(spec: ToolSpec, granted: set[ToolPermission]) -> None:
        missing = [permission for permission in spec.permissions if permission not in granted]
        if missing:
            raise ToolPermissionError(
                f"Missing permissions for {spec.name}: "
                + ", ".join(permission.value for permission in missing),
                details={"missing": [permission.value for permission in missing]},
            )

    @staticmethod
    def _failure(
        context: ToolContext,
        error: HarnessError,
        started: float,
        attempts: int,
    ) -> ToolResult:
        return ToolResult(
            call_id=context.call_id,
            tool_name=context.metadata.get("tool_name", "unknown"),
            ok=False,
            error=error.message,
            error_type=error.code,
            latency_ms=(time.perf_counter() - started) * 1000,
            attempts=attempts,
            retryable=error.retryable,
            metadata={"details": error.details},
        )

    async def _emit(self, event: str, context: ToolContext, payload: dict[str, Any]) -> None:
        if self.event_handler:
            await self.event_handler(event, context, payload)

