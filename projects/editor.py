from __future__ import annotations

from copy import deepcopy
from typing import Any

from pydantic import TypeAdapter

from ai.schemas import OperationPlan, OperationSpec, SupportedPartSpec
from cad.generator import generate_part, generate_step
from cad.operation_executor import execute_operation_plan
from cad.operation_validator import validate_operation_plan
from cad.validator import validate_part
from learning.classifier import classify_failure
from learning.store import LearningStore
from projects.diff import diff_models
from projects.models import (
    AddOperationEdit,
    EditInstruction,
    ModifyOperationEdit,
    RemoveOperationEdit,
    RenameProjectEdit,
    ReorderOperationEdit,
    ReplaceOperationEdit,
    SetParameterEdit,
    SetDesignParameterEdit,
)
from parametrics.resolver import ParametricResolutionError, resolve_design_intent
from projects.revisions import revision_output_path
from projects.serialization import model_from_json, model_to_json, model_type_for
from projects.store import ProjectStore


OPERATION_ADAPTER = TypeAdapter(OperationSpec)


class EditApplicationError(ValueError):
    """Raised when a structured edit cannot be safely applied."""


def apply_edit(current_model: SupportedPartSpec | OperationPlan, edit: EditInstruction) -> tuple[SupportedPartSpec | OperationPlan, str]:
    """Apply a typed edit to a copy of the current structured model."""

    new_model = deepcopy(current_model)
    if isinstance(edit, SetParameterEdit):
        _set_path(new_model, edit.path, edit.value)
    elif isinstance(edit, SetDesignParameterEdit):
        _set_design_parameter(new_model, edit.parameter_id, edit.value)
    elif isinstance(edit, ModifyOperationEdit):
        if not isinstance(new_model, OperationPlan):
            raise EditApplicationError("modify_operation edits require an OperationPlan.")
        _modify_operation(new_model, edit.operation_id, edit.changes)
    elif isinstance(edit, AddOperationEdit):
        if not isinstance(new_model, OperationPlan):
            raise EditApplicationError("add_operation edits require an OperationPlan.")
        _add_operation(new_model, edit.operation, edit.insert_after_id)
    elif isinstance(edit, RemoveOperationEdit):
        if not isinstance(new_model, OperationPlan):
            raise EditApplicationError("remove_operation edits require an OperationPlan.")
        _remove_operation(new_model, edit.operation_id)
    elif isinstance(edit, ReplaceOperationEdit):
        if not isinstance(new_model, OperationPlan):
            raise EditApplicationError("replace_operation edits require an OperationPlan.")
        _replace_operation(new_model, edit.operation_id, edit.operation)
    elif isinstance(edit, ReorderOperationEdit):
        if not isinstance(new_model, OperationPlan):
            raise EditApplicationError("reorder_operation edits require an OperationPlan.")
        _reorder_operation(new_model, edit.operation_id, edit.after_operation_id)
    elif isinstance(edit, RenameProjectEdit):
        if not isinstance(new_model, OperationPlan):
            raise EditApplicationError("rename_project edits currently apply to OperationPlan.project_name.")
        new_model.project_name = edit.name
    else:
        raise EditApplicationError(f"Unsupported edit type: {type(edit).__name__}")

    new_model = _resolve_and_revalidate_model(new_model)
    _validate_and_generate(new_model)
    return new_model, diff_models(current_model, new_model)


def apply_edit_to_project(
    *,
    project_id: str,
    edit: EditInstruction,
    user_instruction: str,
    store: ProjectStore | None = None,
    learning_store: LearningStore | None = None,
) -> tuple[object, str]:
    store = store or ProjectStore()
    learning_store = learning_store or LearningStore()
    current_revision = store.current_revision(project_id)
    if current_revision is None:
        raise EditApplicationError("Project has no current revision.")
    current_model = model_from_json(current_revision.model_type, current_revision.structured_spec_json)

    try:
        new_model, summary = apply_edit(current_model, edit)
        next_number = store.next_revision_number(project_id)
        output_path = revision_output_path(project_id, next_number)
        generate_step(new_model, output_path)
        generate_step(new_model, "outputs/model.step")
        revision = store.add_revision(
            project_id=project_id,
            parent_revision_id=current_revision.revision_id,
            user_instruction=user_instruction,
            model_type=model_type_for(new_model),
            structured_spec_json=model_to_json(new_model),
            change_summary=summary,
            step_output_path=str(output_path),
        )
        return revision, summary
    except Exception as exc:
        learning_store.record_failure(
            error_category=classify_failure(exc),
            error_message=str(exc),
            operation_plan_json=current_revision.structured_spec_json
            if current_revision.model_type == "operation_plan"
            else None,
            parsed_spec_json=current_revision.structured_spec_json
            if current_revision.model_type == "template"
            else None,
        )
        raise


def _set_path(model: SupportedPartSpec | OperationPlan, path: str, value: Any) -> None:
    parts = path.split(".")
    target: Any = model
    for part in parts[:-1]:
        if isinstance(target, OperationPlan) and part == "operations":
            target = {operation.id: operation for operation in target.operations}
        elif part.isdigit():
            target = target[int(part)]
        elif isinstance(target, list):
            target = target[int(part)]
        elif isinstance(target, dict):
            target = target[part]
        else:
            target = getattr(target, part)
    final = parts[-1]
    if isinstance(target, list):
        target[int(final)] = value
    elif isinstance(target, dict):
        target[final] = value
    elif hasattr(target, final):
        setattr(target, final, value)
    else:
        raise EditApplicationError(f"Unknown parameter path: {path}")


def _set_design_parameter(model: SupportedPartSpec | OperationPlan, parameter_id: str, value: float) -> None:
    parameters = getattr(model, "parameters", [])
    for parameter in parameters:
        if parameter.parameter_id == parameter_id:
            if not parameter.editable or parameter.role == "derived":
                raise EditApplicationError(f"Design parameter '{parameter_id}' is derived or locked.")
            parameter.value = value
            return
    raise EditApplicationError(f"Unknown design parameter: {parameter_id}")


def _modify_operation(plan: OperationPlan, operation_id: str, changes: dict[str, Any]) -> None:
    index = _operation_index(plan, operation_id)
    raw = plan.operations[index].model_dump(mode="json")
    raw.update(changes)
    plan.operations[index] = OPERATION_ADAPTER.validate_python(raw)


def _add_operation(plan: OperationPlan, operation: OperationSpec, insert_after_id: str | None) -> None:
    if insert_after_id is None:
        plan.operations.append(operation)
        plan.final_object_id = operation.id
        return
    index = _operation_index(plan, insert_after_id)
    plan.operations.insert(index + 1, operation)
    plan.final_object_id = operation.id


def _remove_operation(plan: OperationPlan, operation_id: str) -> None:
    index = _operation_index(plan, operation_id)
    del plan.operations[index]
    if plan.final_object_id == operation_id:
        plan.final_object_id = plan.operations[-1].id if plan.operations else None


def _replace_operation(plan: OperationPlan, operation_id: str, operation: OperationSpec) -> None:
    index = _operation_index(plan, operation_id)
    plan.operations[index] = operation


def _reorder_operation(plan: OperationPlan, operation_id: str, after_operation_id: str | None) -> None:
    index = _operation_index(plan, operation_id)
    operation = plan.operations.pop(index)
    if after_operation_id is None:
        plan.operations.insert(0, operation)
        return
    after_index = _operation_index(plan, after_operation_id)
    plan.operations.insert(after_index + 1, operation)


def _operation_index(plan: OperationPlan, operation_id: str) -> int:
    for index, operation in enumerate(plan.operations):
        if operation.id == operation_id:
            return index
    raise EditApplicationError(f"Unknown operation id: {operation_id}")


def _revalidate_model(model: SupportedPartSpec | OperationPlan) -> SupportedPartSpec | OperationPlan:
    if isinstance(model, OperationPlan):
        return OperationPlan.model_validate(model.model_dump(mode="json"))
    return type(model).model_validate(model.model_dump(mode="json"))


def _resolve_and_revalidate_model(model: SupportedPartSpec | OperationPlan) -> SupportedPartSpec | OperationPlan:
    try:
        if getattr(model, "parameters", None) or getattr(model, "relationships", None):
            model = resolve_design_intent(model).resolved_model
    except ParametricResolutionError as exc:
        raise EditApplicationError(str(exc)) from exc
    return _revalidate_model(model)


def _validate_and_generate(model: SupportedPartSpec | OperationPlan) -> None:
    if isinstance(model, OperationPlan):
        validate_operation_plan(model)
        execute_operation_plan(model)
    else:
        validate_part(model)
        generate_part(model)
