from __future__ import annotations

from typing import Any

from ai.schemas import OperationPlan, SupportedPartSpec
from projects.serialization import model_to_dict
from projects.store import ProjectStore
from projects.serialization import model_from_json
from parametrics.resolver import resolve_design_intent


def diff_models(before: SupportedPartSpec | OperationPlan, after: SupportedPartSpec | OperationPlan) -> str:
    if getattr(before, "parameters", None) or getattr(before, "relationships", None) or getattr(after, "parameters", None) or getattr(after, "relationships", None):
        return _diff_parametric_models(before, after)
    if isinstance(before, OperationPlan) and isinstance(after, OperationPlan):
        return _diff_operation_plans(before, after)
    return _diff_dicts(model_to_dict(before), model_to_dict(after))


def diff_revisions(
    project_id: str,
    rev_a: int,
    rev_b: int,
    *,
    store: ProjectStore | None = None,
) -> str:
    store = store or ProjectStore()
    a = store.get_revision(project_id, rev_a)
    b = store.get_revision(project_id, rev_b)
    if a is None or b is None:
        raise ValueError("Both revisions must exist.")
    return diff_models(
        model_from_json(a.model_type, a.structured_spec_json),
        model_from_json(b.model_type, b.structured_spec_json),
    )


def _diff_operation_plans(before: OperationPlan, after: OperationPlan) -> str:
    lines: list[str] = []
    before_ops = {op.id: op for op in before.operations}
    after_ops = {op.id: op for op in after.operations}
    for op_id in before_ops.keys() - after_ops.keys():
        lines.append(f"Removed operation: {op_id}")
    for op_id in after_ops.keys() - before_ops.keys():
        op = after_ops[op_id]
        lines.append(f"Added operation: {op_id} ({op.operation_type})")
    for op_id in before_ops.keys() & after_ops.keys():
        changes = _dict_changes(before_ops[op_id].model_dump(mode="json"), after_ops[op_id].model_dump(mode="json"))
        if changes:
            lines.append(f"Modified operation: {op_id}")
            lines.extend(f"  {change}" for change in changes)
    before_order = [op.id for op in before.operations]
    after_order = [op.id for op in after.operations]
    if before_order != after_order:
        lines.append(f"Operation order: {before_order} -> {after_order}")
    if before.final_object_id != after.final_object_id:
        lines.append(f"final_object_id: {before.final_object_id} -> {after.final_object_id}")
    return "\n".join(lines) if lines else "No structured changes."


def _diff_parametric_models(before: SupportedPartSpec | OperationPlan, after: SupportedPartSpec | OperationPlan) -> str:
    lines: list[str] = []
    before_parameters = {parameter.parameter_id: parameter for parameter in getattr(before, "parameters", [])}
    after_parameters = {parameter.parameter_id: parameter for parameter in getattr(after, "parameters", [])}
    driving: list[str] = []
    for parameter_id in sorted(before_parameters.keys() | after_parameters.keys()):
        old = before_parameters.get(parameter_id)
        new = after_parameters.get(parameter_id)
        if old is None:
            driving.append(f"  Added {parameter_id}: {new.value} {new.unit}")  # type: ignore[union-attr]
        elif new is None:
            driving.append(f"  Removed {parameter_id}: {old.value} {old.unit}")
        elif old.value != new.value:
            label = new.name or parameter_id
            role = new.role.upper()
            driving.append(f"  {label} ({role}): {old.value:g} -> {new.value:g} {new.unit}")
    if driving:
        lines.append("DRIVING CHANGES")
        lines.extend(driving)

    try:
        before_resolved = resolve_design_intent(before).resolved_model
        after_resolved = resolve_design_intent(after).resolved_model
        before_data = _without_intent_metadata(model_to_dict(before_resolved))
        after_data = _without_intent_metadata(model_to_dict(after_resolved))
        derived = _dict_changes(before_data, after_data)
    except Exception:
        derived = _dict_changes(_without_intent_metadata(model_to_dict(before)), _without_intent_metadata(model_to_dict(after)))
    if derived:
        lines.append("DERIVED CHANGES")
        lines.extend(f"  {change}" for change in derived)
    return "\n".join(lines) if lines else "No structured changes."


def _without_intent_metadata(data: dict[str, Any]) -> dict[str, Any]:
    clean = dict(data)
    clean.pop("parameters", None)
    clean.pop("relationships", None)
    return clean


def _diff_dicts(before: dict[str, Any], after: dict[str, Any]) -> str:
    changes = _dict_changes(before, after)
    return "\n".join(changes) if changes else "No structured changes."


def _dict_changes(before: dict[str, Any], after: dict[str, Any], prefix: str = "") -> list[str]:
    lines: list[str] = []
    keys = set(before) | set(after)
    for key in sorted(keys):
        path = f"{prefix}.{key}" if prefix else key
        if key not in before:
            lines.append(f"Added {path}: {after[key]}")
        elif key not in after:
            lines.append(f"Removed {path}: {before[key]}")
        elif isinstance(before[key], dict) and isinstance(after[key], dict):
            lines.extend(_dict_changes(before[key], after[key], path))
        elif before[key] != after[key]:
            lines.append(f"{path}: {before[key]} -> {after[key]}")
    return lines
