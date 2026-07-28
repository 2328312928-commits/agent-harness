from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time

from agent_harness.sandbox.base import Sandbox, SandboxResult


class LocalProcessSandbox(Sandbox):
    """Development-only fallback. It does not provide container isolation."""

    def __init__(self, *, default_timeout_seconds: float = 20) -> None:
        self.default_timeout_seconds = default_timeout_seconds

    async def run_python(self, code: str, *, timeout_seconds: float | None = None) -> SandboxResult:
        started = time.perf_counter()
        timeout = timeout_seconds or self.default_timeout_seconds
        with tempfile.TemporaryDirectory(prefix="agent-harness-") as temp_dir:
            process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-I",
                "-c",
                code,
                cwd=temp_dir,
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "PYTHONDONTWRITEBYTECODE": "1",
                    "PYTHONHASHSEED": "0",
                    "TMPDIR": temp_dir,
                },
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
                timed_out = False
            except TimeoutError:
                process.kill()
                stdout, stderr = await process.communicate()
                timed_out = True

        return SandboxResult(
            ok=process.returncode == 0 and not timed_out,
            exit_code=process.returncode,
            stdout=stdout.decode("utf-8", errors="replace")[-100_000:],
            stderr=stderr.decode("utf-8", errors="replace")[-100_000:],
            duration_ms=(time.perf_counter() - started) * 1000,
            timed_out=timed_out,
            backend="local",
            metadata={"warning": "LocalProcessSandbox is not a security boundary."},
        )

    async def health(self) -> dict[str, object]:
        return {
            "backend": "local",
            "ok": True,
            "warning": "Development-only. Container isolation is disabled.",
        }

