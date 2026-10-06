from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from pydantic import BaseModel, ValidationError

from ai.providers.base import AIProvider
from ai.providers.errors import AIProviderTimeoutError, AIProviderUnavailableError, MalformedAIResponseError
from ai.providers.models import AIProviderStatus, EditParseResponse
from ai.providers.prompts import DESIGN_SYSTEM_PROMPT, EDIT_SYSTEM_PROMPT
from ai.schemas import PromptParseResponse
from config import AIProviderConfig


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


class OllamaProvider(AIProvider):
    def __init__(self, config: AIProviderConfig, *, max_attempts: int = 2) -> None:
        self.config = config
        self.max_attempts = max(1, max_attempts)

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.config.ollama_model

    @property
    def endpoint(self) -> str:
        return self.config.ollama_url.rstrip("/")

    def health_check(self) -> AIProviderStatus:
        nonlocal_warning = not _is_local_http_url(self.endpoint)
        if nonlocal_warning:
            return AIProviderStatus(
                provider="ollama",
                label="Local AI / Ollama",
                state="invalid_config",
                ready=False,
                configured=True,
                model=self.model_name,
                endpoint=self.endpoint,
                message="Ollama endpoint must be localhost or 127.0.0.1 unless reviewed before use.",
                nonlocal_endpoint_warning=True,
            )
        try:
            models = self.list_models()
        except AIProviderTimeoutError:
            return AIProviderStatus(
                provider="ollama",
                label="Local AI / Ollama",
                state="timeout",
                ready=False,
                configured=True,
                model=self.model_name,
                endpoint=self.endpoint,
                message=f"Ollama timed out at {self.endpoint}.",
            )
        except AIProviderUnavailableError:
            return AIProviderStatus(
                provider="ollama",
                label="Local AI / Ollama",
                state="server_unavailable",
                ready=False,
                configured=True,
                model=self.model_name,
                endpoint=self.endpoint,
                message=f"Ollama is not responding at {self.endpoint}.",
            )
        if self.model_name not in models:
            return AIProviderStatus(
                provider="ollama",
                label="Local AI / Ollama",
                state="model_unavailable",
                ready=False,
                configured=True,
                model=self.model_name,
                endpoint=self.endpoint,
                available_models=models,
                message=f"Model {self.model_name!r} is not installed in Ollama.",
            )
        return AIProviderStatus(
            provider="ollama",
            label="Local AI / Ollama",
            state="ready",
            ready=True,
            configured=True,
            model=self.model_name,
            endpoint=self.endpoint,
            available_models=models,
            message="Ready",
        )

    def list_models(self) -> list[str]:
        data = self._request("GET", "/api/tags", timeout=min(3.0, self.config.timeout_seconds))
        raw_models = data.get("models", [])
        if not isinstance(raw_models, list):
            return []
        names: list[str] = []
        for item in raw_models:
            if isinstance(item, dict) and isinstance(item.get("name"), str):
                names.append(item["name"])
        return sorted(names)

    def parse_design_prompt(self, prompt: str) -> PromptParseResponse:
        return self._request_structured(
            system_prompt=DESIGN_SYSTEM_PROMPT,
            user_payload=prompt,
            schema=PromptParseResponse,
            schema_name="PromptParseResponse",
        )

    def parse_edit_prompt(
        self,
        *,
        instruction: str,
        current_spec: Any,
        relevant_lessons: list[str],
        enabled_capabilities: list[str],
        current_revision_number: int | None,
    ) -> EditParseResponse:
        payload = {
            "instruction": instruction,
            "current_revision_number": current_revision_number,
            "current_spec": current_spec.model_dump(mode="json") if hasattr(current_spec, "model_dump") else current_spec,
            "relevant_lessons": relevant_lessons[:5],
            "enabled_capabilities": enabled_capabilities,
        }
        return self._request_structured(
            system_prompt=EDIT_SYSTEM_PROMPT,
            user_payload=json.dumps(payload),
            schema=EditParseResponse,
            schema_name="EditParseResponse",
        )

    def _request_structured(
        self,
        *,
        system_prompt: str,
        user_payload: str,
        schema: type[BaseModel],
        schema_name: str,
    ) -> Any:
        if not _is_local_http_url(self.endpoint):
            raise AIProviderUnavailableError("Refusing non-local Ollama endpoint.")
        last_error = ""
        for attempt in range(1, self.max_attempts + 1):
            repair = "" if not last_error else (
                "\nYour previous response failed validation. Return corrected JSON only. "
                f"Validation error: {last_error}"
            )
            content = self._chat(system_prompt, f"{user_payload}{repair}")
            try:
                decoded = json.loads(_strip_json_fences(content))
                return schema.model_validate(decoded)
            except (json.JSONDecodeError, ValidationError, TypeError, ValueError) as exc:
                last_error = str(exc)
                if attempt >= self.max_attempts:
                    raise MalformedAIResponseError(
                        f"Ollama returned invalid {schema_name} JSON after {self.max_attempts} attempts: {last_error}"
                    ) from exc
        raise MalformedAIResponseError(f"Ollama returned invalid {schema_name} JSON.")

    def _chat(self, system_prompt: str, user_content: str) -> str:
        payload = {
            "model": self.model_name,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "options": {"temperature": 0},
        }
        data = self._request("POST", "/api/chat", payload)
        message = data.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
        response = data.get("response")
        if isinstance(response, str):
            return response
        raise MalformedAIResponseError("Ollama response did not include message.content.")

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        timeout: float | None = None,
    ) -> dict[str, Any]:
        url = f"{self.endpoint}{path}"
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.config.timeout_seconds) as response:  # noqa: S310 - URL is config-validated localhost
                raw = response.read().decode("utf-8", errors="replace")
        except TimeoutError as exc:
            raise AIProviderTimeoutError("Ollama request timed out.") from exc
        except socket.timeout as exc:
            raise AIProviderTimeoutError("Ollama request timed out.") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise AIProviderUnavailableError(f"Ollama request failed: {exc}") from exc
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise MalformedAIResponseError("Ollama returned non-JSON data.") from exc
        if not isinstance(parsed, dict):
            raise MalformedAIResponseError("Ollama returned unexpected JSON.")
        return parsed


def _is_local_http_url(raw_url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(raw_url)
    except ValueError:
        return False
    return parsed.scheme == "http" and (parsed.hostname or "") in LOCAL_HOSTS


def _strip_json_fences(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped
