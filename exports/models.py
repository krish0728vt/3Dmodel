from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ExportSourceType(str, Enum):
    PROJECT_REVISION = "project_revision"
    ASSEMBLY_REVISION = "assembly_revision"
    CAPABILITY_OUTPUT = "capability_output"


class ExportFormat(str, Enum):
    STEP = "step"
    STL = "stl"
    DXF = "dxf"
    GLB = "glb"
    OBJ = "obj"
    MANIFEST = "manifest"
    ZIP = "zip"


class StlQuality(str, Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    HIGH = "high"


class ComponentCoordinateMode(str, Enum):
    LOCAL = "local"
    ASSEMBLY_POSITIONED = "assembly_positioned"


class ExportOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stl_quality: StlQuality = StlQuality.STANDARD
    package: bool = False
    include_manifest: bool = True
    component_mode: ComponentCoordinateMode = ComponentCoordinateMode.ASSEMBLY_POSITIONED


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: ExportSourceType
    source_id: str
    revision: int | None = None
    formats: list[ExportFormat]
    options: ExportOptions = Field(default_factory=ExportOptions)


class ExportResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: str | None = None
    format: ExportFormat
    path: str
    filename: str
    size_bytes: int
    checksum_sha256: str
    created_at: str
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportBatchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: ExportRequest
    source_name: str
    revision: int
    revision_id: str | None = None
    output_dir: str
    results: list[ExportResult]
    warnings: list[str] = Field(default_factory=list)


class ExportHistoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    export_id: str
    source_type: ExportSourceType
    source_id: str
    revision: int
    revision_id: str | None = None
    format: ExportFormat
    path: str
    filename: str
    size_bytes: int
    checksum_sha256: str
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)
