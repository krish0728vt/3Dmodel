from __future__ import annotations

from typing import Any

from ai.providers.errors import (
    AIProviderError,
    AIProviderUnavailableError,
    MissingApiKeyError as ProviderMissingApiKeyError,
    MalformedAIResponseError as ProviderMalformedAIResponseError,
)
from ai.providers.registry import active_provider
from ai.schemas import OperationPlan, PromptParseResponse, SupportedDesignSpec
from cad.operation_validator import OperationValidationError, validate_operation_plan
from cad.validator import GeometryValidationError, validate_part
from engineering.units import normalize_prompt_lengths_to_mm


DEFAULT_MODEL = "gpt-5-mini"


class PromptParserError(RuntimeError):
    """Base class for expected prompt parsing failures."""


class MissingApiKeyError(ProviderMissingApiKeyError, PromptParserError):
    """Raised when natural-language parsing is requested without a configured provider."""


class UnsupportedPartError(PromptParserError):
    """Raised when the prompt asks for an unsupported CAD part."""


class MissingInformationError(PromptParserError):
    """Raised when the prompt lacks required engineering dimensions."""


class MalformedAIResponseError(ProviderMalformedAIResponseError, PromptParserError):
    """Raised when the AI response cannot be converted to the parser schema."""


class AIConnectionError(AIProviderUnavailableError, PromptParserError):
    """Raised when the selected AI provider request fails."""


def parse_prompt(
    prompt: str,
    *,
    client: Any | None = None,
    model: str | None = None,
) -> SupportedDesignSpec:
    """Parse natural language into a validated supported CAD part specification."""

    cleaned_prompt = prompt.strip()
    if not cleaned_prompt:
        raise MissingInformationError("Describe a mounting plate before generating a model.")

    normalized_prompt = normalize_prompt_lengths_to_mm(cleaned_prompt)

    response = _request_structured_parse(normalized_prompt, client=client, model=model)
    spec = _spec_from_response(response)
    try:
        if isinstance(spec, OperationPlan):
            validate_operation_plan(spec)
        else:
            validate_part(spec)
    except (GeometryValidationError, OperationValidationError) as exc:
        raise MissingInformationError(str(exc)) from exc
    return spec


def _request_structured_parse(
    prompt: str,
    *,
    client: Any | None,
    model: str | None,
) -> object:
    if client is not None:
        from ai.providers.openai_provider import OpenAIProvider
        from config import ai_provider_config

        return OpenAIProvider(ai_provider_config(), client=client).parse_design_prompt(prompt)
    provider = active_provider()
    try:
        return provider.parse_design_prompt(prompt)
    except ProviderMissingApiKeyError as exc:
        raise MissingApiKeyError(str(exc)) from exc
    except ProviderMalformedAIResponseError as exc:
        raise MalformedAIResponseError(str(exc)) from exc
    except AIProviderUnavailableError as exc:
        raise AIConnectionError(str(exc)) from exc
    except AIProviderError as exc:
        raise PromptParserError(str(exc)) from exc


def _spec_from_response(response: PromptParseResponse) -> SupportedDesignSpec:
    if response.status == "unsupported":
        raise UnsupportedPartError(
            response.message or "This version currently supports rectangular mounting plates only."
        )
    if response.status == "missing_information":
        raise MissingInformationError(response.message or "The prompt is missing required dimensions.")
    if response.spec is None:
        raise MalformedAIResponseError("The parser returned success without a CAD specification.")
    return response.spec
