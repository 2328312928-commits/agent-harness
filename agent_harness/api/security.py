from __future__ import annotations

import asyncio
import secrets
import time
from collections import defaultdict, deque
from typing import TYPE_CHECKING

from fastapi import HTTPException, Request, status

if TYPE_CHECKING:
    from agent_harness.api.container import AppContainer


class SlidingWindowRateLimiter:
    def __init__(self, *, limit: int, window_seconds: float = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        now = time.monotonic()
        async with self._lock:
            events = self._events[key]
            while events and now - events[0] > self.window_seconds:
                events.popleft()
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True


def request_key(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def require_write_access(request: Request) -> None:
    app: AppContainer = request.app.state.container
    settings = app.settings
    if settings.public_demo_mode:
        return
    if settings.api_auth_token:
        provided = request.headers.get("X-API-Key", "")
        if not provided or not secrets.compare_digest(provided, settings.api_auth_token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid X-API-Key",
            )
        return
    if settings.app_env != "production":
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Write API is disabled until API_AUTH_TOKEN or PUBLIC_DEMO_MODE is configured"
        ),
    )
