from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from agent_harness.domain.errors import ProviderError
from agent_harness.domain.models import Message, ProviderResponse, ToolCall, Usage
from agent_harness.providers.base import LLMProvider, ProviderRequest


class RetryableProviderError(ProviderError):
    retryable = True


class OpenAICompatibleProvider(LLMProvider):
    name = "openai-compatible"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: float = 120,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("API key is required for OpenAI-compatible provider")
        if not base_url:
            raise ProviderError("Base URL is required for OpenAI-compatible provider")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def complete(self, request: ProviderRequest) -> ProviderResponse:
        return await self._complete_with_retry(request)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(RetryableProviderError),
        reraise=True,
    )
    async def _complete_with_retry(self, request: ProviderRequest) -> ProviderResponse:
        payload: dict[str, Any] = {
            "model": request.model or self.default_model,
            "messages": [self._serialize_message(message) for message in request.messages],
            "temperature": request.temperature,
            "stream": False,
        }
        if request.max_tokens:
            payload["max_tokens"] = request.max_tokens
        if request.tools:
            payload["tools"] = [tool.as_openai_tool() for tool in request.tools]
            payload["tool_choice"] = "auto"
        if request.response_format:
            payload["response_format"] = request.response_format

        started = time.perf_counter()
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "agent-harness/0.2.1",
        }
        if "opencode.ai" in self.base_url:
            headers["x-opencode-session"] = str(
                request.metadata.get("session_id") or "agent-harness"
            )
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise RetryableProviderError(f"Provider request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RetryableProviderError(f"Provider transport error: {exc}") from exc

        if response.status_code in {408, 409, 429} or response.status_code >= 500:
            raise RetryableProviderError(
                f"Provider returned retryable status {response.status_code}: {response.text[:500]}"
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"Provider returned status {response.status_code}: {response.text[:500]}"
            )

        try:
            body = response.json()
            choice = body["choices"][0]
            message = choice.get("message", {})
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ProviderError(f"Invalid provider response: {response.text[:500]}") from exc

        tool_calls = [
            ToolCall(
                id=item.get("id") or f"call_{index}",
                name=item["function"]["name"],
                arguments=self._parse_arguments(item["function"].get("arguments")),
            )
            for index, item in enumerate(message.get("tool_calls") or [])
            if item.get("function", {}).get("name")
        ]
        usage_data = body.get("usage") or {}
        usage = Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        if usage.total_tokens == 0:
            usage.total_tokens = usage.prompt_tokens + usage.completion_tokens

        return ProviderResponse(
            content=message.get("content") or "",
            reasoning_content=message.get("reasoning_content"),
            tool_calls=tool_calls,
            usage=usage,
            finish_reason=choice.get("finish_reason"),
            model=body.get("model", self.default_model),
            latency_ms=(time.perf_counter() - started) * 1000,
            provider_request_id=response.headers.get("x-request-id"),
        )

    @staticmethod
    def _serialize_message(message: Message) -> dict[str, Any]:
        item: dict[str, Any] = {"role": message.role.value, "content": message.content}
        if message.reasoning_content:
            item["reasoning_content"] = message.reasoning_content
        if message.name:
            item["name"] = message.name
        if message.tool_call_id:
            item["tool_call_id"] = message.tool_call_id
        if message.tool_calls:
            item["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": __import__("json").dumps(call.arguments, ensure_ascii=False),
                    },
                }
                for call in message.tool_calls
            ]
        return item

    @staticmethod
    def _parse_arguments(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = __import__("json").loads(value)
        except (TypeError, ValueError):
            return {"_raw": str(value)}
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
