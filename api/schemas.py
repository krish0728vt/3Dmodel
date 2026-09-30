from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from capabilities.models import CapabilityInvokeRequest
from assemblies.models import AssemblyComponent


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["online"]
    service: str
    route_count: int


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str | None = Field(default=None, description="Natural-language CAD prompt.")
    spec: dict[str, Any] | None = Field(
        default=None,
        description="Structured template spec or operation plan for deterministic generation.",
    )
    project_name: str | None = None
    save_project: bool = True


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    spec: dict[str, Any]
    source_prompt: str | None = None


class ProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    created_at: str
    updated_at: str
    current_revision: int
    source_prompt: str | None = None
    model_type: Literal["template", "operation_plan"]
    status: str
    archived_at: str | None = None
    last_opened_at: str | None = None
    thumbnail_url: str | None = None
    material: str | None = None


class RevisionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    project_id: str
    revision_number: int
    parent_revision_id: str | None = None
    timestamp: str
    user_instruction: str
    model_type: Literal["template", "operation_plan"]
    change_summary: str
    step_output_path: str
    generation_status: str
    validation_status: str


class ProjectDetail(ProjectSummary):
    current_revision_record: RevisionSummary | None = None
    current_model: dict[str, Any] | None = None


class GenerateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project: ProjectSummary | None
    revision: RevisionSummary | None
    spec: dict[str, Any]
    step_url: str | None
    stl_url: str | None
    message: str


class EditProjectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str | None = Field(default=None, description="Natural-language edit instruction.")
    edit: dict[str, Any] | None = Field(default=None, description="Structured edit instruction.")


class EditProjectResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    revision: RevisionSummary
    change_summary: str
    stl_url: str


class DiffResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    from_revision: int
    to_revision: int
    diff: str


class MaterialAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    material_id: str | None = None


class ParameterUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    instruction: str | None = None


class RenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str


class DuplicateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    revision: int | None = None


class DeleteConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmation: Literal["DELETE"]


class ParametricValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    spec: dict[str, Any]


class AssemblyCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    notes: str | None = None
    components: list[AssemblyComponent] = Field(default_factory=list)


class AssemblyEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str | None = None
    edit: dict[str, Any] | None = None


class CapabilityApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved_by: str = "local_user"
    approval_notes: str | None = None


class CapabilityDiscoverRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str | None = None


class CapabilityInvokeApiRequest(CapabilityInvokeRequest):
    pass


class PreviewBoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid")

    xmin: float
    ymin: float
    zmin: float
    xmax: float
    ymax: float
    zmax: float
    xlen: float
    ylen: float
    zlen: float


class SketchPreviewEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    points: list[tuple[float, float, float]]


class PreviewObject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: str
    label: str
    operation_type: str
    object_type: Literal["solid", "sketch", "subtractive_helper", "helper", "final_solid"]
    mesh_url: str | None = None
    bounding_box: PreviewBoundingBox | None = None
    visible_by_default: bool = True
    selectable: bool = True
    source_operation: dict[str, Any] | None = None
    sketch_entities: list[SketchPreviewEntity] = Field(default_factory=list)
    notes: str | None = None


class RevisionPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    revision: int
    preview_format: Literal["semantic-stl-preview"] = "semantic-stl-preview"
    units: Literal["mm"] = "mm"
    final_mesh_url: str
    objects: list[PreviewObject]
    overall_bounding_box: PreviewBoundingBox | None = None
    limitations: list[str] = Field(default_factory=list)
