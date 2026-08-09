from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from agent_harness.api.container import AppContainer
from agent_harness.api.routes import router
from agent_harness.config import get_settings


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)
    container = AppContainer(settings)
    await container.startup()
    app.state.container = container
    try:
        yield
    finally:
        await container.shutdown()


app = FastAPI(
    title="Agent Harness API",
    version="0.1.0",
    description="Checkpointable, observable, and evaluable agent runtime.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "name": "Agent Harness",
        "docs": "/docs",
        "health": "/api/health",
    }

