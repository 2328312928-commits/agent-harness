from __future__ import annotations

import httpx

from agent_harness.domain.models import Message, MessageRole
from agent_harness.providers.base import ProviderRequest
from agent_harness.providers.openai_compatible import OpenAICompatibleProvider


async def test_opencodego_session_header() -> None:
    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update({key.lower(): value for key, value in request.headers.items()})
        return httpx.Response(
            200,
            json={
                "model": "deepseek-v4.1-flash",
                "choices": [
                    {
                        "message": {
                            "content": "ok",
                            "reasoning_content": "private reasoning",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenAICompatibleProvider(
            api_key="test",
            base_url="https://opencode.ai/zen/go/v1",
            model="deepseek-v4.1-flash",
            client=client,
        )
        response = await provider.complete(
            ProviderRequest(
                phase="act",
                messages=[Message(role=MessageRole.USER, content="hello")],
                metadata={"session_id": "task_test"},
            )
        )

    assert captured["x-opencode-session"] == "task_test"
    assert captured["user-agent"] == "agent-harness/0.2.1"
    assert response.reasoning_content == "private reasoning"
