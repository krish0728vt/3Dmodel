from __future__ import annotations

from typing import Any

from pydantic import TypeAdapter

from ai.parser import AIConnectionError, MalformedAIResponseError, MissingApiKeyError
from ai.providers.errors import (
    AIProviderError,
    AIProviderUnavailableError,
    MissingApiKeyError as ProviderMissingApiKeyError,
    MalformedAIResponseError as ProviderMalformedAIResponseError,
)
from ai.providers.models import EditParseResponse
from ai.providers.registry import active_provider
from projects.models import EditInstruction


EDIT_ADAPTER = TypeAdapter(EditInstruction)


class EditParserError(RuntimeError):
    """Base class for expected edit parsing failures."""


class AmbiguousEditError(EditParserError):
    """Raised when an edit request is ambiguous."""


class UnsupportedEditError(EditParserError):
    """Raised when an edit requires unsupported functionality."""


def parse_edit_request(
    instruction: str,
    current_spec: Any,
    *,
    relevant_lessons: list[str] | None = None,
    enabled_capabilities: list[str] | None = None,
    current_revision_number: int | None = None,
    client: Any | None = None,
    model: str | None = None,
) -> EditInstruction:
    """Parse a conversational edit into one safe structured edit instruction."""

    response = _request_edit_parse(
        instruction=instruction,
        current_spec=current_spec,
        relevant_lessons=relevant_lessons or [],
        enabled_capabilities=enabled_capabilities or [],
        current_revision_number=current_revision_number,
        client=client,
        model=model,
    )
    if response.status == "ambiguous":
        raise AmbiguousEditError(response.message)
    if response.status == "unsupported":
        raise UnsupportedEditError(response.message)
    if response.edit is None:
        raise MalformedAIResponseError("Edit parser returned success without an edit.")
    return response.edit


def _request_edit_parse(
    *,
    instruction: str,
    current_spec: Any,
    relevant_lessons: list[str],
    enabled_capabilities: list[str],
    current_revision_number: int | None,
    client: Any | None,
    model: str | None,
) -> EditParseResponse:
    if client is None:
        provider = active_provider()
    else:
        from ai.providers.openai_provider import OpenAIProvider
        from config import ai_provider_config

        provider = OpenAIProvider(ai_provider_config(), client=client)
    try:
        return provider.parse_edit_prompt(
            instruction=instruction,
            current_spec=current_spec,
            relevant_lessons=relevant_lessons,
            enabled_capabilities=enabled_capabilities,
            current_revision_number=current_revision_number,
        )
    except ProviderMissingApiKeyError as exc:
        raise MissingApiKeyError(str(exc)) from exc
    except ProviderMalformedAIResponseError as exc:
        raise MalformedAIResponseError(str(exc)) from exc
    except AIProviderUnavailableError as exc:
        raise AIConnectionError(str(exc)) from exc
    except AIProviderError as exc:
        raise EditParserError(str(exc)) from exc
