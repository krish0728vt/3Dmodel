from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ai.schemas import OperationPlan, SupportedPartSpec
from parametrics.expressions import ExpressionEvaluationError, evaluate_expression, expression_dependencies, literal_or_expression_value
from parametrics.graph import DependencyGraphError, topological_order
from parametrics.models import (
    AlignedRelationship,
    CenteredRelationship,
    DependentDimensionRelationship,
    DesignParameter,
    EdgeOffsetRelationship,
    EqualSpacingRelationship,
    FixedRelationship,
    ParametricRelationship,
    RelativePositionRelationship,
    SymmetricRelationship,
)


class ParametricResolutionError(ValueError):
    """Raised when design intent cannot be deterministically resolved."""


@dataclass(frozen=True)
class ResolvedDesign:
    intent_model: SupportedPartSpec | OperationPlan
    resolved_model: SupportedPartSpec | OperationPlan
    parameters: list[DesignParameter]
    relationships: list[ParametricRelationship]
    resolved_parameters: dict[str, float]
    derived_values: dict[str, float]
    diagnostics: list[str]


def resolve_design_intent(
    structured_model: SupportedPartSpec | OperationPlan,
    parameters: list[DesignParameter] | None = None,
    relationships: list[ParametricRelationship] | None = None,
) -> ResolvedDesign:
    """Resolve typed design intent into ordinary numeric CAD data."""

    intent_model = deepcopy(structured_model)
    resolved_model = deepcopy(structured_model)
    model_parameters = list(parameters if parameters is not None else getattr(resolved_model, "parameters", []))
    model_relationships = list(relationships if relationships is not None else getattr(resolved_model, "relationships", []))
    resolved_parameters = _resolve_parameters(model_parameters, model_relationships)
    updates: dict[str, float] = {}
    diagnostics: list[str] = []
    _resolve_external_capability_arguments(resolved_model, resolved_parameters)

    for parameter in model_parameters:
        path = f"parameters.{parameter.parameter_id}.value"
        updates[path] = resolved_parameters[parameter.parameter_id]
    fixed_updates: dict[str, float] = {}
    for relationship in model_relationships:
        if isinstance(relationship, FixedRelationship):
            _queue_update(
                fixed_updates,
                relationship.target,
                literal_or_expression_value(relationship.value, resolved_parameters),
                relationship.relationship_id,
            )
    for path, value in fixed_updates.items():
        _set_path(resolved_model, path, value)
        updates[path] = value
    for relationship in model_relationships:
        if isinstance(relationship, DependentDimensionRelationship):
            continue
        if isinstance(relationship, FixedRelationship):
            continue
        elif isinstance(relationship, EdgeOffsetRelationship):
            value = _resolve_edge_offset(resolved_model, relationship, resolved_parameters)
            _queue_update(updates, relationship.target, value, relationship.relationship_id)
        elif isinstance(relationship, CenteredRelationship):
            _resolve_centered(resolved_model, relationship, updates)
        elif isinstance(relationship, AlignedRelationship):
            _resolve_aligned(resolved_model, relationship, updates)
        elif isinstance(relationship, SymmetricRelationship):
            _resolve_symmetric(resolved_model, relationship, updates)
        elif isinstance(relationship, EqualSpacingRelationship):
            _resolve_equal_spacing(resolved_model, relationship, resolved_parameters, updates)
        elif isinstance(relationship, RelativePositionRelationship):
            value = _object_coordinate(resolved_model, relationship.reference_id, relationship.axis) + literal_or_expression_value(
                relationship.offset_mm,
                resolved_parameters,
            )
            _queue_update(updates, _coordinate_path(resolved_model, relationship.target_id, relationship.axis), value, relationship.relationship_id)
        else:
            raise ParametricResolutionError(f"Unsupported relationship type: {type(relationship).__name__}")

    derived_values: dict[str, float] = {}
    for path, value in updates.items():
        if path.startswith("parameters."):
            _set_parameter_value(resolved_model, path, value)
        else:
            _set_path(resolved_model, path, value)
            derived_values[path] = value
    diagnostics.append(f"Resolved {len(model_parameters)} parameters and {len(model_relationships)} relationships.")
    return ResolvedDesign(
        intent_model=intent_model,
        resolved_model=resolved_model,
        parameters=model_parameters,
        relationships=model_relationships,
        resolved_parameters=resolved_parameters,
        derived_values=derived_values,
        diagnostics=diagnostics,
    )


def has_design_intent(model: SupportedPartSpec | OperationPlan) -> bool:
    return bool(getattr(model, "parameters", None) or getattr(model, "relationships", None))


def resolved_model(model: SupportedPartSpec | OperationPlan) -> SupportedPartSpec | OperationPlan:
    if not has_design_intent(model):
        return model
    return resolve_design_intent(model).resolved_model


def _resolve_parameters(parameters: list[DesignParameter], relationships: list[ParametricRelationship]) -> dict[str, float]:
    values = {parameter.parameter_id: float(parameter.value) for parameter in parameters}
    parameter_ids = set(values)
    dependent = [relationship for relationship in relationships if isinstance(relationship, DependentDimensionRelationship)]
    dependencies: dict[str, set[str]] = {}
    by_target: dict[str, DependentDimensionRelationship] = {}
    for relationship in dependent:
        if relationship.target_parameter not in parameter_ids:
            raise ParametricResolutionError(f"MISSING PARAMETER: {relationship.target_parameter}")
        deps = expression_dependencies(relationship.expression)
        missing = deps - parameter_ids
        if missing:
            raise ParametricResolutionError("MISSING PARAMETER: " + ", ".join(sorted(missing)))
        dependencies[relationship.target_parameter] = deps
        by_target[relationship.target_parameter] = relationship
    try:
        order = topological_order(dependencies)
        for parameter_id in order:
            values[parameter_id] = evaluate_expression(by_target[parameter_id].expression, values)
    except (DependencyGraphError, ExpressionEvaluationError) as exc:
        raise ParametricResolutionError(str(exc)) from exc
    return values


def _queue_update(updates: dict[str, float], path: str, value: float, relationship_id: str) -> None:
    value = round(float(value), 6)
    if path in updates and abs(updates[path] - value) > 1e-6:
        raise ParametricResolutionError(
            f"CONSTRAINT CONFLICT: {path} already resolves to {updates[path]}, "
            f"but {relationship_id} resolves to {value}."
        )
    updates[path] = value


def _resolve_edge_offset(model: SupportedPartSpec | OperationPlan, relationship: EdgeOffsetRelationship, parameters: dict[str, float]) -> float:
    bounds = _object_bounds(model, relationship.reference_object)
    offset = literal_or_expression_value(relationship.offset_mm, parameters)
    if relationship.reference_edge == "left":
        return bounds["xmin"] + offset
    if relationship.reference_edge == "right":
        return bounds["xmax"] - offset
    if relationship.reference_edge == "bottom":
        return bounds["ymin"] + offset
    if relationship.reference_edge == "top":
        return bounds["ymax"] - offset
    if relationship.reference_edge == "front":
        return bounds["zmax"] - offset
    if relationship.reference_edge == "back":
        return bounds["zmin"] + offset
    raise ParametricResolutionError(f"Unsupported reference edge: {relationship.reference_edge}")


def _resolve_centered(model: SupportedPartSpec | OperationPlan, relationship: CenteredRelationship, updates: dict[str, float]) -> None:
    axes = _axes(relationship.axes)
    for axis in axes:
        path = _coordinate_path(model, relationship.target_id, axis)
        _queue_update(updates, path, _object_coordinate(model, relationship.reference_id, axis), relationship.relationship_id)


def _resolve_aligned(model: SupportedPartSpec | OperationPlan, relationship: AlignedRelationship, updates: dict[str, float]) -> None:
    for axis in relationship.axes:
        path = _coordinate_path(model, relationship.target_id, axis)
        _queue_update(updates, path, _object_coordinate(model, relationship.reference_id, axis), relationship.relationship_id)


def _resolve_symmetric(model: SupportedPartSpec | OperationPlan, relationship: SymmetricRelationship, updates: dict[str, float]) -> None:
    first_id, second_id = relationship.target_ids
    center = _object_coordinate(model, relationship.reference_object, relationship.axis)
    first_path = _coordinate_path(model, first_id, relationship.axis)
    second_path = _coordinate_path(model, second_id, relationship.axis)
    first_value = _get_path(model, first_path)
    second_value = 2 * center - float(first_value)
    _queue_update(updates, second_path, second_value, relationship.relationship_id)


def _resolve_equal_spacing(
    model: SupportedPartSpec | OperationPlan,
    relationship: EqualSpacingRelationship,
    parameters: dict[str, float],
    updates: dict[str, float],
) -> None:
    if not relationship.target_ids:
        return
    start = literal_or_expression_value(relationship.start, parameters)
    end = literal_or_expression_value(relationship.end, parameters)
    count = len(relationship.target_ids)
    values = [start] if count == 1 else [start + index * (end - start) / (count - 1) for index in range(count)]
    for target_id, value in zip(relationship.target_ids, values):
        _queue_update(updates, _coordinate_path(model, target_id, relationship.axis), value, relationship.relationship_id)


def _axes(value: str) -> list[str]:
    if value == "xy":
        return ["x", "y"]
    if value == "xyz":
        return ["x", "y", "z"]
    return [value]


def _object_bounds(model: SupportedPartSpec | OperationPlan, object_id: str) -> dict[str, float]:
    if object_id == "model":
        data = model.model_dump(mode="json")
        if data.get("part_type") == "mounting_plate":
            return _bounds_from_center_dims((0, 0, 0), data["width_mm"], data["height_mm"], data["thickness_mm"])
        if data.get("part_type") == "box":
            return _bounds_from_center_dims((0, 0, 0), data["width_mm"], data["depth_mm"], data["height_mm"])
        if data.get("part_type") == "electronics_enclosure":
            outer_width = data["internal_width_mm"] + 2 * data["wall_thickness_mm"]
            outer_depth = data["internal_depth_mm"] + 2 * data["wall_thickness_mm"]
            outer_height = data["internal_height_mm"] + data["bottom_thickness_mm"]
            return _bounds_from_center_dims((0, 0, outer_height / 2), outer_width, outer_depth, outer_height)
    operation = _operation(model, object_id)
    if operation is None:
        raise ParametricResolutionError(f"MISSING PARAMETER: reference object '{object_id}' was not found.")
    data = operation.model_dump(mode="json")
    center = data.get("center") or data.get("position") or [0, 0, 0]
    center3 = _point3(center)
    op_type = data.get("operation_type")
    if op_type == "create_box":
        return _bounds_from_center_dims(center3, data["width_mm"], data["depth_mm"], data["height_mm"])
    if op_type == "create_cylinder":
        diameter = data["diameter_mm"]
        return _bounds_from_center_dims(center3, diameter, diameter, data["height_mm"])
    if op_type in {"boss", "through_hole", "blind_hole", "counterbore_hole", "countersink_hole", "cut_hole"}:
        diameter = data.get("diameter_mm") or data.get("hole_diameter_mm") or data.get("counterbore_diameter_mm") or 0
        height = data.get("height_mm") or data.get("depth_mm") or 0
        return _bounds_from_center_dims(center3, diameter, diameter, height)
    raise ParametricResolutionError(f"Unsupported reference object for parametric bounds: {object_id}")


def _bounds_from_center_dims(center: tuple[float, float, float], xlen: float, ylen: float, zlen: float) -> dict[str, float]:
    return {
        "xmin": center[0] - xlen / 2,
        "xmax": center[0] + xlen / 2,
        "ymin": center[1] - ylen / 2,
        "ymax": center[1] + ylen / 2,
        "zmin": center[2] - zlen / 2,
        "zmax": center[2] + zlen / 2,
    }


def _object_coordinate(model: SupportedPartSpec | OperationPlan, object_id: str, axis: str) -> float:
    bounds = _object_bounds(model, object_id)
    if axis == "x":
        return (bounds["xmin"] + bounds["xmax"]) / 2
    if axis == "y":
        return (bounds["ymin"] + bounds["ymax"]) / 2
    if axis == "z":
        return (bounds["zmin"] + bounds["zmax"]) / 2
    raise ParametricResolutionError(f"Unsupported axis: {axis}")


def _coordinate_path(model: SupportedPartSpec | OperationPlan, object_id: str, axis: str) -> str:
    operation = _operation(model, object_id)
    if operation is None:
        raise ParametricResolutionError(f"MISSING PARAMETER: target object '{object_id}' was not found.")
    data = operation.model_dump(mode="json")
    root = "center" if "center" in data else "position" if "position" in data else None
    if root is None:
        raise ParametricResolutionError(f"Object '{object_id}' has no editable center or position.")
    index = {"x": 0, "y": 1, "z": 2}[axis]
    if root == "position" and axis == "z":
        raise ParametricResolutionError(f"Object '{object_id}' has only a 2D position.")
    return f"operations.{object_id}.{root}.{index}"


def _operation(model: SupportedPartSpec | OperationPlan, operation_id: str) -> Any | None:
    if not isinstance(model, OperationPlan):
        return None
    for operation in model.operations:
        if operation.id == operation_id:
            return operation
    return None


def _resolve_external_capability_arguments(model: SupportedPartSpec | OperationPlan, parameters: dict[str, float]) -> None:
    if not isinstance(model, OperationPlan):
        return
    for operation in model.operations:
        data = operation.model_dump(mode="json")
        if data.get("operation_type") == "external_capability":
            operation.arguments = _resolve_argument_value(operation.arguments, parameters)


def _resolve_argument_value(value: Any, parameters: dict[str, float]) -> Any:
    if isinstance(value, dict):
        if set(value) == {"parameter_ref"}:
            parameter_id = value["parameter_ref"]
            if parameter_id not in parameters:
                raise ParametricResolutionError(f"MISSING PARAMETER: {parameter_id}")
            return parameters[parameter_id]
        return {key: _resolve_argument_value(child, parameters) for key, child in value.items()}
    if isinstance(value, list):
        return [_resolve_argument_value(child, parameters) for child in value]
    return value


def _point3(value: list[float] | tuple[float, ...]) -> tuple[float, float, float]:
    if len(value) == 2:
        return (float(value[0]), float(value[1]), 0.0)
    return (float(value[0]), float(value[1]), float(value[2]))


def _get_path(model: SupportedPartSpec | OperationPlan, path: str) -> Any:
    target, final = _path_parent(model, path)
    if isinstance(target, list):
        return target[int(final)]
    if isinstance(target, dict):
        return target[final]
    return getattr(target, final)


def _set_path(model: SupportedPartSpec | OperationPlan, path: str, value: float) -> None:
    _set_nested(model, path.split("."), value)


def _set_nested(target: Any, parts: list[str], value: float) -> Any:
    part = parts[0]
    if isinstance(target, OperationPlan) and part == "operations":
        if len(parts) < 2:
            raise ParametricResolutionError("Invalid operation path.")
        operation_id = parts[1]
        operation = _operation(target, operation_id)
        if operation is None:
            raise ParametricResolutionError(f"MISSING PARAMETER: target object '{operation_id}' was not found.")
        _set_nested(operation, parts[2:], value)
        return target
    if len(parts) == 1:
        if isinstance(target, list):
            target[int(part)] = value
            return target
        if isinstance(target, tuple):
            values = list(target)
            values[int(part)] = value
            return tuple(values)
        if isinstance(target, dict):
            target[part] = value
            return target
        setattr(target, part, value)
        return target

    child = _path_next(target, part)
    updated_child = _set_nested(child, parts[1:], value)
    if isinstance(target, list):
        target[int(part)] = updated_child
    elif isinstance(target, tuple):
        values = list(target)
        values[int(part)] = updated_child
        return tuple(values)
    elif isinstance(target, dict):
        target[part] = updated_child
    else:
        setattr(target, part, updated_child)
    return target


def _path_parent(model: SupportedPartSpec | OperationPlan, path: str) -> tuple[Any, str]:
    parts = path.split(".")
    target: Any = model
    for part in parts[:-1]:
        target = _path_next(target, part)
    return target, parts[-1]


def _path_next(target: Any, part: str) -> Any:
    if isinstance(target, OperationPlan) and part == "operations":
        return {operation.id: operation for operation in target.operations}
    if part.isdigit():
        return target[int(part)]
    if isinstance(target, list):
        return target[int(part)]
    if isinstance(target, tuple):
        return list(target)
    if isinstance(target, dict):
        return target[part]
    return getattr(target, part)


def _set_parameter_value(model: SupportedPartSpec | OperationPlan, path: str, value: float) -> None:
    _, parameter_id, field_name = path.split(".", 2)
    if field_name != "value":
        raise ParametricResolutionError(f"Unsupported parameter path: {path}")
    for parameter in getattr(model, "parameters", []):
        if parameter.parameter_id == parameter_id:
            parameter.value = value
            return
    raise ParametricResolutionError(f"MISSING PARAMETER: {parameter_id}")
