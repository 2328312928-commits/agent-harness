from __future__ import annotations

from agent_harness.config import Settings
from agent_harness.domain.errors import ProviderError
from agent_harness.providers.base import LLMProvider
from agent_harness.providers.deepseek import DeepSeekProvider
from agent_harness.providers.fake import FakeProvider
from agent_harness.providers.openai_compatible import OpenAICompatibleProvider


class ProviderRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._providers: dict[str, LLMProvider] = {}

    def get(self, name: str | None = None) -> LLMProvider:
        provider_name = name or self.settings.default_provider
        if provider_name in self._providers:
            return self._providers[provider_name]

        if provider_name == "fake":
            provider: LLMProvider = FakeProvider()
        elif provider_name == "deepseek":
            provider = DeepSeekProvider(
                api_key=self.settings.deepseek_api_key,
                base_url=self.settings.deepseek_base_url,
                model=self.settings.deepseek_model,
                timeout_seconds=self.settings.provider_request_timeout_seconds,
                max_retries=self.settings.provider_max_retries,
            )
        elif provider_name == "openai-compatible":
            provider = OpenAICompatibleProvider(
                api_key=self.settings.openai_compatible_api_key,
                base_url=self.settings.openai_compatible_base_url,
                model=self.settings.openai_compatible_model,
                timeout_seconds=self.settings.provider_request_timeout_seconds,
                max_retries=self.settings.provider_max_retries,
            )
        else:
            raise ProviderError(f"Unknown provider: {provider_name}")

        self._providers[provider_name] = provider
        return provider

    def catalog(self) -> list[dict[str, object]]:
        return [
            {
                "name": "fake",
                "configured": True,
                "default_model": "fake-deterministic-v1",
                "purpose": "Offline demo, tests, and deterministic harness regression.",
            },
            {
                "name": "deepseek",
                "configured": bool(self.settings.deepseek_api_key),
                "default_model": self.settings.deepseek_model,
                "purpose": "DeepSeek chat and reasoning APIs.",
            },
            {
                "name": "openai-compatible",
                "configured": bool(
                    self.settings.openai_compatible_api_key
                    and self.settings.openai_compatible_base_url
                    and self.settings.openai_compatible_model
                ),
                "default_model": self.settings.openai_compatible_model,
                "purpose": "Any OpenAI-compatible endpoint.",
            },
        ]

    async def close(self) -> None:
        for provider in self._providers.values():
            await provider.close()
        self._providers.clear()

