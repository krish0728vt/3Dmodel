from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ComponentSourceType(str, Enum):
    PROJECT_REVISION = "project_revision"
    GENERATED_FILE = "generated_file"
    CAPABILITY_OUTPUT = "capability_output"
    IMPORTED_FILE = "imported_file"


class InterferenceStatus(str, Enum):
    NO_OVERLAP = "NO_OVERLAP"
    POSSIBLE_OVERLAP = "POSSIBLE_OVERLAP"
    CONFIRMED_INTERFERENCE = "CONFIRMED_INTERFERENCE"


class AssemblyStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Transform(BaseModel):
    model_config = ConfigDict(extra="forbid")

    translation_x_mm: float = 0
    translation_y_mm: float = 0
    translation_z_mm: float = 0
    rotation_x_deg: float = 0
    rotation_y_deg: float = 0
    rotation_z_deg: float = 0


class AssemblyComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    name: str
    source_type: ComponentSourceType = ComponentSourceType.PROJECT_REVISION
    project_id: str | None = None
    project_revision: int | None = None
    capability_output: dict[str, Any] | None = None
    external_step_path: str | None = None
    external_stl_path: str | None = None
    transform: Transform = Field(default_factory=Transform)
    visible: bool = True
    grounded: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssemblyRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembly_id: str
    name: str
    created_at: str
    updated_at: str
    current_revision: int = 0
    notes: str | None = None
    status: AssemblyStatus = AssemblyStatus.ACTIVE
    archived_at: str | None = None
    last_opened_at: str | None = None


class AssemblyRevisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    assembly_id: str
    revision_number: int
    parent_revision_id: str | None = None
    timestamp: str
    user_instruction: str
    change_summary: str
    components: list[AssemblyComponent]
    manifest_path: str | None = None


class AddComponentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["add_component"] = "add_component"
    component: AssemblyComponent


class RemoveComponentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["remove_component"] = "remove_component"
    component_id: str


class MoveComponentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["move_component"] = "move_component"
    component_id: str
    dx_mm: float = 0
    dy_mm: float = 0
    dz_mm: float = 0


class RotateComponentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["rotate_component"] = "rotate_component"
    component_id: str
    rx_deg: float = 0
    ry_deg: float = 0
    rz_deg: float = 0


class SetTransformEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["set_transform"] = "set_transform"
    component_id: str
    transform: Transform


class SetVisibilityEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["set_visibility"] = "set_visibility"
    component_id: str
    visible: bool


class SetGroundedEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["set_grounded"] = "set_grounded"
    component_id: str
    grounded: bool


class RenameComponentEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["rename_component"] = "rename_component"
    component_id: str
    name: str


class RenameAssemblyEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["rename_assembly"] = "rename_assembly"
    name: str


AssemblyEdit = Annotated[
    AddComponentEdit
    | RemoveComponentEdit
    | MoveComponentEdit
    | RotateComponentEdit
    | SetTransformEdit
    | SetVisibilityEdit
    | SetGroundedEdit
    | RenameComponentEdit
    | RenameAssemblyEdit,
    Field(discriminator="edit_type"),
]


class BoundingBox(BaseModel):
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


class ComponentPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    name: str
    source_type: ComponentSourceType
    mesh_url: str | None
    transform: Transform
    visible: bool
    grounded: bool
    bounding_box: BoundingBox | None = None


class AssemblyPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembly_id: str
    revision: int
    components: list[ComponentPreview]
    bounding_box: BoundingBox | None = None


class ComponentEngineeringSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component_id: str
    name: str
    bounding_box: BoundingBox | None = None
    mass_g: float | None = None
    center_of_mass: tuple[float, float, float] | None = None
    material_id: str | None = None


class InterferenceResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_component_id: str
    second_component_id: str
    status: InterferenceStatus
    method: str = "world_bounding_box_overlap"


class AssemblyEngineeringSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assembly_id: str
    revision: int
    component_count: int
    component_summaries: list[ComponentEngineeringSummary] = Field(default_factory=list)
    bounding_box: BoundingBox | None = None
    known_mass_g: float
    unknown_mass_components: list[str]
    center_of_mass: tuple[float, float, float] | None = None
    center_of_mass_status: Literal["available", "partial", "unavailable"]
    interferences: list[InterferenceResult]
