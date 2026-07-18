from __future__ import annotations

from typing import Any


class HarnessError(Exception):
    code = "harness_error"
    retryable = False

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(HarnessError):
    code = "validation_error"


class ToolNotFoundError(HarnessError):
    code = "tool_not_found"


class ToolPermissionError(HarnessError):
    code = "tool_permission_denied"


class ToolTimeoutError(HarnessError):
    code = "tool_timeout"
    retryable = True


class ToolCancelledError(HarnessError):
    code = "tool_cancelled"


class CheckpointNotFoundError(HarnessError):
    code = "checkpoint_not_found"


class TaskNotFoundError(HarnessError):
    code = "task_not_found"


class ProviderError(HarnessError):
    code = "provider_error"

