from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Agent Harness"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://localhost:8080"

    database_url: str = "sqlite+aiosqlite:///./data/harness.db"
    redis_url: str = "redis://localhost:6379/0"

    default_provider: Literal["fake", "deepseek", "openai-compatible"] = "fake"
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"
    openai_compatible_api_key: str = ""
    openai_compatible_base_url: str = ""
    openai_compatible_model: str = ""
    provider_request_timeout_seconds: float = 120
    provider_max_retries: int = 3

    token_budget: int = 32_000
    summary_trigger_tokens: int = 24_000
    long_term_memory_enabled: bool = True

    workspace_root: Path = Path("./workspace")
    tool_default_timeout_seconds: float = 30
    tool_max_retries: int = 2
    allow_local_code_execution: bool = False
    github_token: str = ""
    database_readonly_url: str = ""

    sandbox_backend: Literal["docker", "local"] = "docker"
    sandbox_image: str = "python:3.12-alpine"
    sandbox_memory_limit: str = "256m"
    sandbox_cpu_limit: float = 1.0
    sandbox_timeout_seconds: float = 20
    sandbox_network_disabled: bool = True

    mcp_servers_json: list[dict] = Field(default_factory=list)

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+asyncpg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+asyncpg://", 1)
        return value

    @field_validator("mcp_servers_json", mode="before")
    @classmethod
    def parse_mcp_servers(cls, value: object) -> object:
        if value in (None, ""):
            return []
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def resolved_workspace_root(self) -> Path:
        return self.workspace_root.expanduser().resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
