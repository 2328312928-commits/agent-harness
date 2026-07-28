from __future__ import annotations

import asyncio
import time
from typing import Any

from agent_harness.sandbox.base import Sandbox, SandboxResult


class DockerSandbox(Sandbox):
    def __init__(
        self,
        *,
        image: str = "python:3.12-alpine",
        memory_limit: str = "256m",
        cpu_limit: float = 1.0,
        default_timeout_seconds: float = 20,
        network_disabled: bool = True,
        client: Any | None = None,
    ) -> None:
        self.image = image
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit
        self.default_timeout_seconds = default_timeout_seconds
        self.network_disabled = network_disabled
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            try:
                import docker
            except ImportError as exc:
                raise RuntimeError("docker Python package is not installed") from exc
            self._client = docker.from_env()
        return self._client

    async def run_python(self, code: str, *, timeout_seconds: float | None = None) -> SandboxResult:
        return await asyncio.to_thread(
            self._run_python_sync,
            code,
            timeout_seconds or self.default_timeout_seconds,
        )

    def _run_python_sync(self, code: str, timeout_seconds: float) -> SandboxResult:
        started = time.perf_counter()
        container = None
        try:
            self._ensure_image()
            container = self.client.containers.create(
                self.image,
                command=["python", "-c", code],
                network_disabled=self.network_disabled,
                mem_limit=self.memory_limit,
                nano_cpus=int(self.cpu_limit * 1_000_000_000),
                pids_limit=128,
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
                working_dir="/tmp",
                user="65534:65534",
                cap_drop=["ALL"],
                security_opt=["no-new-privileges:true"],
                environment={"PYTHONDONTWRITEBYTECODE": "1"},
                labels={"agent-harness.sandbox": "true"},
            )
            container.start()
            try:
                wait_result = container.wait(timeout=timeout_seconds)
                timed_out = False
                exit_code = int(wait_result.get("StatusCode", -1))
            except Exception:
                container.kill()
                timed_out = True
                exit_code = None

            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
            return SandboxResult(
                ok=exit_code == 0 and not timed_out,
                exit_code=exit_code,
                stdout=stdout[-100_000:],
                stderr=stderr[-100_000:],
                duration_ms=(time.perf_counter() - started) * 1000,
                timed_out=timed_out,
                backend="docker",
                metadata={
                    "image": self.image,
                    "network_disabled": self.network_disabled,
                    "memory_limit": self.memory_limit,
                    "cpu_limit": self.cpu_limit,
                },
            )
        except Exception as exc:  # noqa: BLE001 - Docker errors vary by platform and daemon.
            return SandboxResult(
                ok=False,
                stderr=f"{type(exc).__name__}: {exc}",
                duration_ms=(time.perf_counter() - started) * 1000,
                backend="docker",
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:  # noqa: BLE001
                    pass

    def _ensure_image(self) -> None:
        try:
            self.client.images.get(self.image)
        except Exception:
            self.client.images.pull(self.image)

    async def health(self) -> dict[str, object]:
        try:
            info = await asyncio.to_thread(self.client.ping)
            image_found = await asyncio.to_thread(self.client.images.get, self.image)
            return {
                "backend": "docker",
                "ok": bool(info),
                "image": self.image,
                "image_available": bool(image_found),
            }
        except Exception as exc:  # noqa: BLE001
            return {"backend": "docker", "ok": False, "error": str(exc)}

