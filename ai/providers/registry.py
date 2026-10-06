from __future__ import annotations

from ai.providers.base import AIProvider
from ai.providers.errors import AIProviderUnavailableError
from ai.providers.models import AIProviderStatus, AIProviderSummary
from ai.providers.ollama_provider import OllamaProvider
from ai.providers.openai_provider import OpenAIProvider
from config import ai_provider_config


class DisabledAIProvider(AIProvider):
    @property
    def provider_name(self) -> str:
        return "none"

    @property
    def model_name(self) -> None:
        return None

    def health_check(self) -> AIProviderStatus:
        return AIProviderStatus(
            provider="none",
            label="AI Disabled",
            state="disabled",
            ready=False,
            configured=True,
            message="AI provider is disabled. Manual deterministic CAD remains available.",
        )

    def parse_design_prompt(self, prompt: str):  # type: ignore[no-untyped-def]
        raise AIProviderUnavailableError("AI provider is disabled. Use manual CAD or select a provider.")

    def parse_edit_prompt(self, **kwargs):  # type: ignore[no-untyped-def]
        raise AIProviderUnavailableError("AI provider is disabled. Use structured edits or select a provider.")


def active_provider() -> AIProvider:
    config = ai_provider_config()
    if config.provider == "openai":
        return OpenAIProvider(config)
    if config.provider == "ollama":
        return OllamaProvider(config)
    return DisabledAIProvider()


def provider_status() -> AIProviderStatus:
    return active_provider().health_check()


def provider_summary() -> AIProviderSummary:
    config = ai_provider_config()
    providers = [
        OpenAIProvider(config).health_check(),
        OllamaProvider(config).health_check(),
        DisabledAIProvider().health_check(),
    ]
    active = next((provider for provider in providers if provider.provider == config.provider), providers[-1])
    return AIProviderSummary(providers=providers, active=active)
