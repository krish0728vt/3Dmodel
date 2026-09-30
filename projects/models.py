from __future__ import annotations

from enum import Enum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ai.schemas import OperationSpec


class ProjectStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    FAILED = "failed"


class GenerationStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"


class ValidationStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"


class ProjectRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str
    name: str
    created_at: str
    updated_at: str
    current_revision: int
    source_prompt: str | None = None
    model_type: Literal["template", "operation_plan"]
    status: ProjectStatus = ProjectStatus.ACTIVE
    archived_at: str | None = None
    last_opened_at: str | None = None
    notes: str | None = None


class RevisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision_id: str
    project_id: str
    revision_number: int
    parent_revision_id: str | None = None
    timestamp: str
    user_instruction: str
    model_type: Literal["template", "operation_plan"]
    structured_spec_json: str
    change_summary: str
    step_output_path: str
    generation_status: GenerationStatus
    validation_status: ValidationStatus
    failure_id: str | None = None
    repair_id: str | None = None


class SetParameterEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["set_parameter"] = "set_parameter"
    path: str
    value: Any


class SetDesignParameterEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["set_design_parameter"] = "set_design_parameter"
    parameter_id: str
    value: float


class ModifyOperationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["modify_operation"] = "modify_operation"
    operation_id: str
    changes: dict[str, Any]


class AddOperationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["add_operation"] = "add_operation"
    operation: OperationSpec
    insert_after_id: str | None = None


class RemoveOperationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["remove_operation"] = "remove_operation"
    operation_id: str


class ReplaceOperationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["replace_operation"] = "replace_operation"
    operation_id: str
    operation: OperationSpec


class ReorderOperationEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["reorder_operation"] = "reorder_operation"
    operation_id: str
    after_operation_id: str | None = None


class RenameProjectEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edit_type: Literal["rename_project"] = "rename_project"
    name: str


EditInstruction = Annotated[
    SetParameterEdit
    | SetDesignParameterEdit
    | ModifyOperationEdit
    | AddOperationEdit
    | RemoveOperationEdit
    | ReplaceOperationEdit
    | ReorderOperationEdit
    | RenameProjectEdit,
    Field(discriminator="edit_type"),
]
