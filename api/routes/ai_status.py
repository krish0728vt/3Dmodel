from __future__ import annotations

from fastapi import APIRouter

from ai.providers.registry import provider_status, provider_summary


router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.get("/status")
def ai_status() -> dict[str, object]:
    return provider_status().model_dump(mode="json")


@router.get("/providers")
def ai_providers() -> dict[str, object]:
    return provider_summary().model_dump(mode="json")


@router.post("/test")
def test_ai_provider() -> dict[str, object]:
    return provider_status().model_dump(mode="json")


@router.get("/ollama/models")
def ollama_models() -> dict[str, object]:
    summary = provider_summary()
    ollama = next((item for item in summary.providers if item.provider == "ollama"), None)
    return {
        "provider": "ollama",
        "endpoint": ollama.endpoint if ollama else None,
        "configured_model": ollama.model if ollama else None,
        "available_models": ollama.available_models if ollama else [],
        "state": ollama.state if ollama else "server_unavailable",
        "ready": ollama.ready if ollama else False,
        "message": ollama.message if ollama else "Ollama status unavailable.",
    }
