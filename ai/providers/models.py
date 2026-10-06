from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from projects.models import EditInstruction


AIProviderName = Literal["openai", "ollama", "none"]
AIProviderState = Literal[
    "ready",
    "disabled",
    "missing_config",
    "server_unavailable",
    "model_unavailable",
    "timeout",
    "invalid_config",
]


class EditParseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["success", "ambiguous", "unsupported"]
    message: str
    edit: EditInstruction | None = None


class AIProviderStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: AIProviderName
    label: str
    state: AIProviderState
    ready: bool
    model: str | None = None
    endpoint: str | None = None
    configured: bool = False
    message: str
    available_models: list[str] = Field(default_factory=list)
    nonlocal_endpoint_warning: bool = False


class AIProviderSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    providers: list[AIProviderStatus]
    active: AIProviderStatus
