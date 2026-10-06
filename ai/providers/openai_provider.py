from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from ai.providers.base import AIProvider
from ai.providers.errors import AIProviderUnavailableError, MissingApiKeyError, MalformedAIResponseError
from ai.providers.models import AIProviderStatus, EditParseResponse
from ai.providers.prompts import DESIGN_SYSTEM_PROMPT, EDIT_SYSTEM_PROMPT
from ai.schemas import PromptParseResponse
from config import AIProviderConfig, openai_key_configured


class OpenAIProvider(AIProvider):
    def __init__(self, config: AIProviderConfig, client: Any | None = None) -> None:
        self.config = config
        self._client = client

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self.config.openai_model

    def health_check(self) -> AIProviderStatus:
        configured = openai_key_configured()
        return AIProviderStatus(
            provider="openai",
            label="OpenAI",
            state="ready" if configured else "missing_config",
            ready=configured,
            configured=configured,
            model=self.model_name,
            message="Configured" if configured else "OPENAI_API_KEY is not configured.",
        )

    def parse_design_prompt(self, prompt: str) -> PromptParseResponse:
        client = self._client or self._build_client()
        try:
            if hasattr(client.responses, "parse"):
                response = client.responses.parse(
                    model=self.model_name,
                    input=[
                        {"role": "system", "content": DESIGN_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    text_format=PromptParseResponse,
                )
            else:
                response = client.responses.create(
                    model=self.model_name,
                    input=[
                        {"role": "system", "content": DESIGN_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "cad_prompt_parse",
                            "schema": PromptParseResponse.model_json_schema(),
                            "strict": True,
                        }
                    },
                )
        except Exception as exc:  # noqa: BLE001 - provider wrappers normalize SDK failures
            raise AIProviderUnavailableError(f"OpenAI API request failed: {exc}") from exc
        return _coerce_prompt_response(response)

    def parse_edit_prompt(
        self,
        *,
        instruction: str,
        current_spec: Any,
        relevant_lessons: list[str],
        enabled_capabilities: list[str],
        current_revision_number: int | None,
    ) -> EditParseResponse:
        client = self._client or self._build_client()
        payload = {
            "instruction": instruction,
            "current_revision_number": current_revision_number,
            "current_spec": current_spec.model_dump(mode="json") if hasattr(current_spec, "model_dump") else current_spec,
            "relevant_lessons": relevant_lessons[:5],
            "enabled_capabilities": enabled_capabilities,
        }
        try:
            response = client.responses.parse(
                model=self.model_name,
                input=[
                    {"role": "system", "content": EDIT_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)},
                ],
                text_format=EditParseResponse,
            )
        except Exception as exc:  # noqa: BLE001
            raise AIProviderUnavailableError(f"OpenAI edit parser request failed: {exc}") from exc
        return _coerce_edit_response(response)

    def _build_client(self) -> Any:
        if not openai_key_configured():
            raise MissingApiKeyError(
                "OPENAI_API_KEY is not set. Configure OpenAI, select Ollama, or use manual mode."
            )
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise MissingApiKeyError("The openai package is not installed.") from exc
        return OpenAI()


def _coerce_prompt_response(response: Any) -> PromptParseResponse:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return _coerce_prompt_value(parsed)

    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            parsed = getattr(content_item, "parsed", None)
            if parsed is not None:
                return _coerce_prompt_value(parsed)

    output_text = getattr(response, "output_text", None)
    if output_text:
        return _coerce_prompt_value(output_text)
    raise MalformedAIResponseError("The parser response did not contain structured CAD data.")


def _coerce_edit_response(response: Any) -> EditParseResponse:
    parsed = getattr(response, "output_parsed", None)
    if parsed is not None:
        return _coerce_edit_value(parsed)
    output_text = getattr(response, "output_text", None)
    if output_text:
        return _coerce_edit_value(output_text)
    raise MalformedAIResponseError("Edit parser response did not contain structured data.")


def _coerce_prompt_value(value: Any) -> PromptParseResponse:
    try:
        if isinstance(value, PromptParseResponse):
            return value
        if isinstance(value, str):
            return PromptParseResponse.model_validate_json(value)
        if isinstance(value, dict):
            return PromptParseResponse.model_validate(value)
        return PromptParseResponse.model_validate(json.loads(json.dumps(value)))
    except (TypeError, ValueError, ValidationError) as exc:
        raise MalformedAIResponseError(f"Malformed parser response: {exc}") from exc


def _coerce_edit_value(value: Any) -> EditParseResponse:
    try:
        if isinstance(value, EditParseResponse):
            return value
        if isinstance(value, str):
            return EditParseResponse.model_validate_json(value)
        if isinstance(value, dict):
            return EditParseResponse.model_validate(value)
        return EditParseResponse.model_validate(json.loads(json.dumps(value)))
    except (TypeError, ValueError, ValidationError) as exc:
        raise MalformedAIResponseError(f"Malformed edit parser response: {exc}") from exc
