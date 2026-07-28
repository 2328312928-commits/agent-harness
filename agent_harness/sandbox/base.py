from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class SandboxResult(BaseModel):
    ok: bool
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_ms: float = 0
    timed_out: bool = False
    backend: str
    metadata: dict[str, object] = Field(default_factory=dict)


class Sandbox(ABC):
    @abstractmethod
    async def run_python(self, code: str, *, timeout_seconds: float | None = None) -> SandboxResult:
        raise NotImplementedError

    async def health(self) -> dict[str, object]:
        return {"backend": self.__class__.__name__, "ok": True}

