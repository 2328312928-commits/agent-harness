from __future__ import annotations

import httpx

from agent_harness.providers.openai_compatible import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    name = "deepseek"

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-chat",
        base_url: str = "https://api.deepseek.com",
        timeout_seconds: float = 120,
        max_retries: int = 3,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        super().__init__(
            api_key=api_key,
            base_url=base_url,
            model=model,
            timeout_seconds=timeout_seconds,
            max_retries=max_retries,
            client=client,
        )

    async def health(self) -> dict[str, object]:
        return {
            "provider": self.name,
            "model": self.default_model,
            "ok": bool(self.api_key),
            "base_url": self.base_url,
        }

