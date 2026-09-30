from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TrustLevel(str, Enum):
    CORE = "CORE"
    APPROVED = "APPROVED"
    EXPERIMENTAL = "EXPERIMENTAL"
    DISABLED = "DISABLED"


class ValidationStatus(str, Enum):
    UNTESTED = "UNTESTED"
    PASSED = "PASSED"
    FAILED = "FAILED"
    NEEDS_RETEST = "NEEDS_RETEST"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class ProviderType(str, Enum):
    CORE = "CORE"
    LOCAL_MANIFEST = "LOCAL_MANIFEST"
    MCP = "MCP"
    HTTP_API = "HTTP_API"
    LOCAL_ADAPTER = "LOCAL_ADAPTER"


class DiscoverySourceType(str, Enum):
    LOCAL_MANIFEST = "local_manifest"
    MCP_SERVER = "mcp_server"
    CURATED_REGISTRY = "curated_registry"
    MANUAL_URL = "manual_url"
    LOCAL_ADAPTER = "local_adapter"


class CapabilityErrorCategory(str, Enum):
    CONNECTION_FAILURE = "capability_connection_failure"
    TIMEOUT = "capability_timeout"
    SCHEMA_FAILURE = "capability_schema_failure"
    EXECUTION_FAILURE = "capability_execution_failure"
    OUTPUT_VALIDATION_FAILURE = "capability_output_validation_failure"
    PERMISSION_FAILURE = "capability_permission_failure"


class DiscoverySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    name: str
    source_type: DiscoverySourceType
    location: str
    enabled: bool = True
    trusted: bool = False
    notes: str | None = None


class CapabilityMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    invocation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_success_at: str | None = None
    last_failure_at: str | None = None


class CapabilityInvocationLog(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    operation: str
    status: Literal["success", "failure"]
    duration_ms: int
    error_category: CapabilityErrorCategory | None = None
    timestamp: str


class CapabilityManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    name: str
    version: str
    description: str = ""
    source: str = "manual_manifest"
    provider_type: ProviderType | str = ProviderType.LOCAL_MANIFEST
    supported_operations: list[str] = Field(default_factory=list)
    required_dependencies: list[str] = Field(default_factory=list)
    trust_level: TrustLevel = TrustLevel.EXPERIMENTAL
    endpoint: str | None = None
    documentation_url: str | None = None
    author: str | None = None
    publisher: str | None = None
    license: str | None = None
    checksum: str | None = None
    compatibility_version: str | None = None
    risk_notes: str | None = None
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    output_type: Literal["metadata", "geometry"] = "metadata"
    local_adapter: str | None = None
    mcp_server_id: str | None = None
    mcp_tool_name: str | None = None
    http_method: Literal["GET", "POST"] = "POST"
    token_env: str | None = None

    @field_validator("provider_type", mode="before")
    @classmethod
    def normalize_provider_type(cls, value: object) -> object:
        if value == "core":
            return ProviderType.CORE
        if value == "external":
            return ProviderType.LOCAL_MANIFEST
        if isinstance(value, str):
            upper = value.upper()
            if upper in ProviderType.__members__:
                return ProviderType[upper]
        return value


class CapabilityRecord(CapabilityManifest):
    enabled: bool = False
    validation_status: ValidationStatus = ValidationStatus.UNTESTED
    discovered_at: str | None = None
    last_checked_at: str | None = None
    last_tested_at: str | None = None
    approved_at: str | None = None
    approved_by: str | None = None
    approval_notes: str | None = None
    metrics: CapabilityMetrics = Field(default_factory=CapabilityMetrics)


class CapabilityInvokeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    arguments: dict[str, Any]


class CapabilityInvokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    result: dict[str, Any]
    duration_ms: int


class GeometryCapabilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    result_type: Literal["geometry"] = "geometry"
    step_path: str | None = None
    stl_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    units: Literal["mm"] = "mm"
