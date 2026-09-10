from __future__ import annotations

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from agent_harness.api.container import AppContainer
from agent_harness.api.routes import router


def api_app(container: AppContainer) -> FastAPI:
    app = FastAPI()
    app.state.container = container
    app.include_router(router)
    return app


async def request(container: AppContainer, headers: dict[str, str] | None = None):
    app = api_app(container)
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test", headers=headers)


async def test_public_demo_restricts_provider_permissions(container: AppContainer) -> None:
    container.settings.public_demo_mode = True
    container.settings.allow_tool_playground = False
    container.rate_limiter.limit = 10
    async with await request(container) as client:
        response = await client.post(
            "/api/tasks",
            json={
                "goal": "请读取 examples/demo.txt",
                "provider": "fake",
                "metadata": {"tool_permissions": ["execute", "write"]},
            },
        )
        assert response.status_code == 202
        payload = response.json()
        assert payload["provider"] == "fake"
        assert payload["metadata"]["tool_permissions"] == [
            "read",
            "network",
            "database",
            "github",
            "browser",
        ]

        denied = await client.post(
            "/api/tasks",
            json={"goal": "test", "provider": "deepseek"},
        )
        assert denied.status_code == 403

        playground = await client.post(
            "/api/tools/playground",
            json={"tool": "filesystem.read_file", "arguments": {}},
        )
        assert playground.status_code == 403


async def test_production_write_api_requires_key(container: AppContainer) -> None:
    container.settings.public_demo_mode = False
    container.settings.app_env = "production"
    container.settings.api_auth_token = "test-secret"
    async with await request(container) as client:
        denied = await client.post(
            "/api/tasks",
            json={"goal": "请列出目录 . 下的文件列表", "provider": "fake"},
        )
        assert denied.status_code == 401

        allowed = await client.post(
            "/api/tasks",
            headers={"X-API-Key": "test-secret"},
            json={"goal": "请列出目录 . 下的文件列表", "provider": "fake"},
        )
        assert allowed.status_code == 202


async def test_public_demo_rate_limit(container: AppContainer) -> None:
    container.settings.public_demo_mode = True
    container.rate_limiter.limit = 1
    async with await request(container) as client:
        first = await client.post(
            "/api/tasks",
            json={"goal": "请列出目录 . 下的文件列表", "provider": "fake"},
        )
        second = await client.post(
            "/api/tasks",
            json={"goal": "请列出目录 . 下的文件列表", "provider": "fake"},
        )
        assert first.status_code == 202
        assert second.status_code == 429

