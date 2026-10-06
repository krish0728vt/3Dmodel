from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.server import create_app
from ai.providers.models import AIProviderStatus, AIProviderSummary


@pytest.fixture
def api_only_client():
    return TestClient(create_app())


def ready_ollama_status() -> AIProviderStatus:
    return AIProviderStatus(
        provider="ollama",
        label="Local AI / Ollama",
        state="ready",
        ready=True,
        configured=True,
        model="qwen2.5-coder:7b",
        endpoint="http://127.0.0.1:11434",
        message="Ready",
        available_models=["qwen2.5-coder:7b"],
    )


def disabled_status() -> AIProviderStatus:
    return AIProviderStatus(
        provider="none",
        label="AI Disabled",
        state="disabled",
        ready=False,
        configured=True,
        message="AI provider is disabled.",
    )


def test_ai_status_endpoint_reports_active_provider(api_only_client, monkeypatch):
    from api.routes import ai_status as route

    monkeypatch.setattr(route, "provider_status", ready_ollama_status)

    response = api_only_client.get("/api/ai/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "ollama"
    assert payload["label"] == "Local AI / Ollama"
    assert payload["ready"] is True
    assert payload["model"] == "qwen2.5-coder:7b"
    assert payload["endpoint"] == "http://127.0.0.1:11434"


def test_ai_providers_endpoint_reports_summary(api_only_client, monkeypatch):
    from api.routes import ai_status as route

    ollama = ready_ollama_status()
    summary = AIProviderSummary(providers=[ollama, disabled_status()], active=ollama)
    monkeypatch.setattr(route, "provider_summary", lambda: summary)

    payload = api_only_client.get("/api/ai/providers").json()

    assert payload["active"]["provider"] == "ollama"
    assert payload["providers"][0]["available_models"] == ["qwen2.5-coder:7b"]


def test_ai_test_endpoint_does_not_depend_on_core_health(api_only_client, monkeypatch):
    from api.routes import ai_status as route

    offline = ready_ollama_status().model_copy(
        update={
            "state": "server_unavailable",
            "ready": False,
            "message": "Ollama is not responding at http://127.0.0.1:11434.",
        }
    )
    monkeypatch.setattr(route, "provider_status", lambda: offline)

    assert api_only_client.get("/api/health").json()["status"] == "online"
    payload = api_only_client.post("/api/ai/test").json()
    assert payload["ready"] is False
    assert payload["state"] == "server_unavailable"


def test_ai_ollama_models_endpoint_returns_only_provider_metadata(api_only_client, monkeypatch):
    from api.routes import ai_status as route

    ollama = ready_ollama_status()
    summary = AIProviderSummary(providers=[ollama, disabled_status()], active=ollama)
    monkeypatch.setattr(route, "provider_summary", lambda: summary)

    payload = api_only_client.get("/api/ai/ollama/models").json()

    assert payload == {
        "provider": "ollama",
        "endpoint": "http://127.0.0.1:11434",
        "configured_model": "qwen2.5-coder:7b",
        "available_models": ["qwen2.5-coder:7b"],
        "state": "ready",
        "ready": True,
        "message": "Ready",
    }


def test_ai_cli_status_succeeds_for_disabled_provider(monkeypatch, capsys):
    import app as app_module
    from ai.providers import registry

    monkeypatch.setattr(registry, "provider_status", disabled_status)

    assert app_module.main(["ai", "status"]) == 0
    output = capsys.readouterr().out
    assert "Provider: AI Disabled" in output


def test_ai_cli_test_fails_for_unavailable_ollama(monkeypatch, capsys):
    import app as app_module
    from ai.providers import registry

    offline = ready_ollama_status().model_copy(update={"ready": False, "state": "server_unavailable"})
    monkeypatch.setattr(registry, "provider_status", lambda: offline)

    assert app_module.main(["ai", "test"]) == 1
    assert '"state": "server_unavailable"' in capsys.readouterr().out
