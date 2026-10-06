from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ai.providers.models import AIProviderStatus, EditParseResponse
from ai.schemas import PromptParseResponse


class AIProvider(ABC):
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Stable provider id."""

    @property
    @abstractmethod
    def model_name(self) -> str | None:
        """Configured model name, when relevant."""

    @abstractmethod
    def health_check(self) -> AIProviderStatus:
        """Cheap readiness check that never exposes secrets."""

    @abstractmethod
    def parse_design_prompt(self, prompt: str) -> PromptParseResponse:
        """Return a strict typed design parse response."""

    @abstractmethod
    def parse_edit_prompt(
        self,
        *,
        instruction: str,
        current_spec: Any,
        relevant_lessons: list[str],
        enabled_capabilities: list[str],
        current_revision_number: int | None,
    ) -> EditParseResponse:
        """Return a strict typed edit parse response."""
