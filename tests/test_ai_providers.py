from __future__ import annotations

import socket
import urllib.error

import pytest

from ai.providers.errors import AIProviderTimeoutError, AIProviderUnavailableError, MalformedAIResponseError
from ai.providers.ollama_provider import OllamaProvider
from ai.providers.openai_provider import OpenAIProvider
from ai.providers.registry import active_provider
from ai.schemas import PromptParseResponse
from config import AIProviderConfig, ai_provider_config


def provider_config(provider: str = "ollama", model: str = "qwen2.5-coder:7b") -> AIProviderConfig:
    return AIProviderConfig(
        provider=provider,  # type: ignore[arg-type]
        provider_source="environment",
        openai_model="gpt-5-mini",
        ollama_url="http://127.0.0.1:11434",
        ollama_model=model,
        timeout_seconds=3,
    )


def test_provider_selection_explicit_none(monkeypatch):
    monkeypatch.setenv("SHAH_AI_PROVIDER", "none")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    config = ai_provider_config()

    assert config.provider == "none"
    assert active_provider().provider_name == "none"


def test_provider_selection_does_not_fallback_from_ollama_to_openai(monkeypatch):
    monkeypatch.setenv("SHAH_AI_PROVIDER", "ollama")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    assert ai_provider_config().provider == "ollama"
    assert active_provider().provider_name == "ollama"


def test_openai_provider_reports_missing_key(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda *_args, **_kwargs: False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status = OpenAIProvider(provider_config("openai")).health_check()

    assert status.provider == "openai"
    assert status.ready is False
    assert status.state == "missing_config"


def test_openai_provider_returns_typed_prompt_response():
    class Responses:
        def parse(self, **_kwargs):  # noqa: ANN001
            return type(
                "Response",
                (),
                {
                    "output_parsed": {
                        "status": "success",
                        "message": "ok",
                        "spec": {
                            "part_type": "box",
                            "width_mm": 10,
                            "depth_mm": 20,
                            "height_mm": 5,
                        },
                    }
                },
            )()

    client = type("Client", (), {"responses": Responses()})()
    parsed = OpenAIProvider(provider_config("openai"), client=client).parse_design_prompt("make a box")

    assert isinstance(parsed, PromptParseResponse)
    assert parsed.status == "success"
    assert parsed.spec is not None
    assert getattr(parsed.spec, "part_type") == "box"


def test_ollama_health_ready_when_model_exists(monkeypatch):
    provider = OllamaProvider(provider_config())
    monkeypatch.setattr(provider, "list_models", lambda: ["qwen2.5-coder:7b"])

    status = provider.health_check()

    assert status.ready is True
    assert status.state == "ready"
    assert status.model == "qwen2.5-coder:7b"


def test_ollama_health_reports_model_missing(monkeypatch):
    provider = OllamaProvider(provider_config(model="missing:latest"))
    monkeypatch.setattr(provider, "list_models", lambda: ["qwen2.5-coder:7b"])

    status = provider.health_check()

    assert status.ready is False
    assert status.state == "model_unavailable"


def test_ollama_server_unavailable(monkeypatch):
    provider = OllamaProvider(provider_config())

    def unavailable() -> list[str]:
        raise AIProviderUnavailableError("connection refused")

    monkeypatch.setattr(provider, "list_models", unavailable)

    status = provider.health_check()

    assert status.ready is False
    assert status.state == "server_unavailable"


def test_ollama_timeout(monkeypatch):
    provider = OllamaProvider(provider_config())

    def timeout() -> list[str]:
        raise AIProviderTimeoutError("slow")

    monkeypatch.setattr(provider, "list_models", timeout)

    status = provider.health_check()

    assert status.ready is False
    assert status.state == "timeout"


def test_ollama_refuses_nonlocal_endpoint():
    config = provider_config()
    config = AIProviderConfig(
        provider=config.provider,
        provider_source=config.provider_source,
        openai_model=config.openai_model,
        ollama_url="https://example.com",
        ollama_model=config.ollama_model,
        timeout_seconds=config.timeout_seconds,
    )
    provider = OllamaProvider(config)

    status = provider.health_check()

    assert status.ready is False
    assert status.state == "invalid_config"
    assert status.nonlocal_endpoint_warning is True


def test_ollama_valid_structured_json(monkeypatch):
    provider = OllamaProvider(provider_config())
    monkeypatch.setattr(
        provider,
        "_chat",
        lambda *_: '{"status":"success","message":"ok","spec":{"part_type":"box","width_mm":10,"depth_mm":20,"height_mm":5}}',
    )

    parsed = provider.parse_design_prompt("make a box")

    assert parsed.status == "success"
    assert parsed.spec is not None
    assert getattr(parsed.spec, "part_type") == "box"


def test_ollama_invalid_json_retries_to_success(monkeypatch):
    provider = OllamaProvider(provider_config(), max_attempts=2)
    responses = iter([
        "not json",
        '{"status":"success","message":"ok","spec":{"part_type":"box","width_mm":10,"depth_mm":20,"height_mm":5}}',
    ])
    monkeypatch.setattr(provider, "_chat", lambda *_: next(responses))

    parsed = provider.parse_design_prompt("make a box")

    assert parsed.status == "success"


def test_ollama_invalid_json_retry_failure(monkeypatch):
    provider = OllamaProvider(provider_config(), max_attempts=2)
    monkeypatch.setattr(provider, "_chat", lambda *_: "not json")

    with pytest.raises(MalformedAIResponseError, match="invalid PromptParseResponse"):
        provider.parse_design_prompt("make a box")


def test_ollama_schema_invalid_response(monkeypatch):
    provider = OllamaProvider(provider_config(), max_attempts=1)
    monkeypatch.setattr(provider, "_chat", lambda *_: '{"status":"maybe","message":"bad status"}')

    with pytest.raises(MalformedAIResponseError):
        provider.parse_design_prompt("make a box")


def test_ollama_request_timeout(monkeypatch):
    provider = OllamaProvider(provider_config())

    def fake_urlopen(*args, **kwargs):  # noqa: ANN001
        raise socket.timeout("timed out")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(AIProviderTimeoutError):
        provider.list_models()


def test_ollama_request_unavailable(monkeypatch):
    provider = OllamaProvider(provider_config())

    def fake_urlopen(*args, **kwargs):  # noqa: ANN001
        raise urllib.error.URLError("refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    with pytest.raises(AIProviderUnavailableError):
        provider.list_models()
