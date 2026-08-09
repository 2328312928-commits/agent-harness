from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class TaskCreateRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=20_000)
    provider: Literal["fake", "deepseek", "openai-compatible"] | None = None
    model: str | None = None
    max_steps: int = Field(default=20, ge=1, le=100)
    token_budget: int = Field(default=32_000, ge=1_000, le=1_000_000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvalRunRequest(BaseModel):
    provider: Literal["fake", "deepseek", "openai-compatible"] | None = None
    model: str | None = None
    strategy: str = "react"
    categories: list[str] = Field(default_factory=list)
    limit: int = Field(default=120, ge=1, le=300)
    offset: int = Field(default=0, ge=0)
    concurrency: int = Field(default=3, ge=1, le=20)


class PlaygroundRequest(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ApiMessage(BaseModel):
    message: str

