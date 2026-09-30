from __future__ import annotations

from ai.schemas import (
    ArcEntity,
    BlindHoleOperation,
    BooleanCutOperation,
    BooleanUnionOperation,
    BossOperation,
    ChamferOperation,
    CircleEntity,
    CircularHolePatternOperation,
    CircularPatternOperation,
    CounterboreHoleOperation,
    CountersinkHoleOperation,
    CreateBoxOperation,
    CreateCylinderOperation,
    CreateSketchOperation,
    CreateSketchCircleOperation,
    CreateSketchRectangleOperation,
    CutExtrudeOperation,
    CutHoleOperation,
    ExtrudeOperation,
    ExternalCapabilityOperation,
    FilletOperation,
    LineEntity,
    LinearPatternOperation,
    LoftOperation,
    MirrorOperation,
    OperationPlan,
    PolygonEntity,
    PolylineEntity,
    RectangleEntity,
    RectangularHolePatternOperation,
    RibOperation,
    RevolveOperation,
    ShellOperation,
    SlotEntity,
    SweepOperation,
    ThroughHoleOperation,
)
from parametrics.resolver import resolved_model


class OperationValidationError(ValueError):
    """Raised when an operation plan cannot be safely executed."""


def validate_operation_plan(plan: OperationPlan) -> None:
    """Validate operation IDs, references, object kinds, and operation dimensions."""

    plan = resolved_model(plan)  # type: ignore[assignment]
    errors: list[str] = []
    if not plan.project_name.strip():
        errors.append("project_name must not be empty.")
    if not plan.operations:
        errors.append("operations must contain at least one operation.")

    object_kinds: dict[str, str] = {}
    for index, operation in enumerate(plan.operations, start=1):
        if not operation.id.strip():
            errors.append(f"operations[{index}].id must not be empty.")
            continue
        if operation.id in object_kinds:
            errors.append(f"operations[{index}] uses duplicate id '{operation.id}'.")
            continue

        errors.extend(_validate_operation_fields(operation, index))
        errors.extend(_validate_operation_references(operation, object_kinds, index))
        object_kinds[operation.id] = _output_kind(operation)

    if plan.final_object_id is not None:
        if plan.final_object_id not in object_kinds:
            errors.append(f"final_object_id '{plan.final_object_id}' does not reference an operation.")
        elif object_kinds[plan.final_object_id] != "solid":
            errors.append(f"final_object_id '{plan.final_object_id}' must reference a solid.")
    elif object_kinds and list(object_kinds.values())[-1] != "solid":
        errors.append("The final operation must produce a solid when final_object_id is not set.")

    if errors:
        raise OperationValidationError("Invalid operation plan: " + " ".join(errors))


def _validate_operation_fields(operation: object, index: int) -> list[str]:
    prefix = f"operations[{index}]"
    errors: list[str] = []

    if isinstance(operation, CreateBoxOperation):
        _positive(errors, prefix, "width_mm", operation.width_mm)
        _positive(errors, prefix, "depth_mm", operation.depth_mm)
        _positive(errors, prefix, "height_mm", operation.height_mm)
    elif isinstance(operation, CreateCylinderOperation):
        _positive(errors, prefix, "diameter_mm", operation.diameter_mm)
        _positive(errors, prefix, "height_mm", operation.height_mm)
    elif isinstance(operation, CreateSketchRectangleOperation):
        _positive(errors, prefix, "width_mm", operation.width_mm)
        _positive(errors, prefix, "height_mm", operation.height_mm)
    elif isinstance(operation, CreateSketchCircleOperation):
        _positive(errors, prefix, "diameter_mm", operation.diameter_mm)
    elif isinstance(operation, CreateSketchOperation):
        errors.extend(_validate_sketch_operation(operation, prefix))
    elif isinstance(operation, ExtrudeOperation):
        _positive(errors, prefix, "distance_mm", operation.distance_mm)
    elif isinstance(operation, RevolveOperation):
        if operation.angle_deg <= 0 or operation.angle_deg > 360:
            errors.append(f"{prefix}.angle_deg must be greater than 0 and at most 360.")
    elif isinstance(operation, CutHoleOperation):
        _positive(errors, prefix, "diameter_mm", operation.diameter_mm)
        if operation.depth_mm is not None:
            _positive(errors, prefix, "depth_mm", operation.depth_mm)
    elif isinstance(operation, CutExtrudeOperation):
        if operation.extent_type == "blind":
            if operation.distance_mm is None:
                errors.append(f"{prefix}.distance_mm is required for blind cut_extrude.")
            else:
                _positive(errors, prefix, "distance_mm", operation.distance_mm)
    elif isinstance(operation, LoftOperation):
        if len(operation.sketch_ids) < 2:
            errors.append(f"{prefix}.sketch_ids must contain at least two sketches.")
    elif isinstance(operation, ShellOperation):
        _positive(errors, prefix, "thickness_mm", operation.thickness_mm)
    elif isinstance(operation, SweepOperation):
        if operation.profile_sketch_id == operation.path_sketch_id:
            errors.append(f"{prefix} profile_sketch_id and path_sketch_id must be different.")
    elif isinstance(operation, (ThroughHoleOperation, BlindHoleOperation)):
        _positive(errors, prefix, "hole_diameter_mm", operation.hole_diameter_mm)
        if isinstance(operation, BlindHoleOperation):
            _positive(errors, prefix, "depth_mm", operation.depth_mm)
    elif isinstance(operation, CounterboreHoleOperation):
        _positive(errors, prefix, "hole_diameter_mm", operation.hole_diameter_mm)
        _positive(errors, prefix, "counterbore_diameter_mm", operation.counterbore_diameter_mm)
        _positive(errors, prefix, "counterbore_depth_mm", operation.counterbore_depth_mm)
        if operation.counterbore_diameter_mm <= operation.hole_diameter_mm:
            errors.append(f"{prefix}.counterbore_diameter_mm must be greater than hole_diameter_mm.")
    elif isinstance(operation, CountersinkHoleOperation):
        _positive(errors, prefix, "hole_diameter_mm", operation.hole_diameter_mm)
        _positive(errors, prefix, "countersink_diameter_mm", operation.countersink_diameter_mm)
        if operation.countersink_diameter_mm <= operation.hole_diameter_mm:
            errors.append(f"{prefix}.countersink_diameter_mm must be greater than hole_diameter_mm.")
        if operation.angle_deg <= 0 or operation.angle_deg >= 180:
            errors.append(f"{prefix}.angle_deg must be greater than 0 and less than 180.")
    elif isinstance(operation, BossOperation):
        _positive(errors, prefix, "diameter_mm", operation.diameter_mm)
        _positive(errors, prefix, "height_mm", operation.height_mm)
    elif isinstance(operation, RibOperation):
        _positive(errors, prefix, "thickness_mm", operation.thickness_mm)
        _positive(errors, prefix, "height_mm", operation.height_mm)
        if operation.start == operation.end:
            errors.append(f"{prefix}.start and end must be different.")
    elif isinstance(operation, RectangularHolePatternOperation):
        _positive(errors, prefix, "hole_diameter_mm", operation.hole_diameter_mm)
        _positive(errors, prefix, "spacing_x_mm", operation.spacing_x_mm)
        _positive(errors, prefix, "spacing_y_mm", operation.spacing_y_mm)
        if operation.count_x < 1 or operation.count_y < 1:
            errors.append(f"{prefix}.count_x and count_y must be at least 1.")
    elif isinstance(operation, CircularHolePatternOperation):
        _positive(errors, prefix, "hole_diameter_mm", operation.hole_diameter_mm)
        _positive(errors, prefix, "radius_mm", operation.radius_mm)
        if operation.count < 2:
            errors.append(f"{prefix}.count must be at least 2.")
    elif isinstance(operation, (BooleanUnionOperation, BooleanCutOperation)):
        if operation.target_id == operation.tool_id:
            errors.append(f"{prefix} target_id and tool_id must reference different objects.")
    elif isinstance(operation, FilletOperation):
        _positive(errors, prefix, "radius_mm", operation.radius_mm)
    elif isinstance(operation, ChamferOperation):
        _positive(errors, prefix, "distance_mm", operation.distance_mm)
    elif isinstance(operation, LinearPatternOperation):
        _positive(errors, prefix, "spacing_mm", operation.spacing_mm)
        if operation.count < 2:
            errors.append(f"{prefix}.count must be at least 2.")
    elif isinstance(operation, CircularPatternOperation):
        if operation.count < 2:
            errors.append(f"{prefix}.count must be at least 2.")
        if operation.angle_deg <= 0 or operation.angle_deg > 360:
            errors.append(f"{prefix}.angle_deg must be greater than 0 and at most 360.")
    elif isinstance(operation, ExternalCapabilityOperation):
        if not operation.capability_id.strip():
            errors.append(f"{prefix}.capability_id must not be empty.")
        if not isinstance(operation.arguments, dict):
            errors.append(f"{prefix}.arguments must be an object.")

    return errors


def _validate_operation_references(
    operation: object,
    object_kinds: dict[str, str],
    index: int,
) -> list[str]:
    prefix = f"operations[{index}]"
    errors: list[str] = []

    if isinstance(operation, (ExtrudeOperation, RevolveOperation)):
        errors.extend(_require_kind(object_kinds, operation.sketch_id, "sketch", prefix, "sketch_id"))
    elif isinstance(operation, CutExtrudeOperation):
        errors.extend(_require_kind(object_kinds, operation.target_id, "solid", prefix, "target_id"))
        errors.extend(_require_kind(object_kinds, operation.sketch_id, "sketch", prefix, "sketch_id"))
    elif isinstance(operation, LoftOperation):
        for sketch_id in operation.sketch_ids:
            errors.extend(_require_kind(object_kinds, sketch_id, "sketch", prefix, "sketch_ids"))
    elif isinstance(operation, SweepOperation):
        errors.extend(_require_kind(object_kinds, operation.profile_sketch_id, "sketch", prefix, "profile_sketch_id"))
        errors.extend(_require_kind(object_kinds, operation.path_sketch_id, "sketch", prefix, "path_sketch_id"))
    elif isinstance(operation, CutHoleOperation):
        errors.extend(_require_kind(object_kinds, operation.target_id, "solid", prefix, "target_id"))
    elif isinstance(operation, (BooleanUnionOperation, BooleanCutOperation)):
        errors.extend(_require_kind(object_kinds, operation.target_id, "solid", prefix, "target_id"))
        errors.extend(_require_kind(object_kinds, operation.tool_id, "solid", prefix, "tool_id"))
    elif isinstance(
        operation,
        (
            FilletOperation,
            ChamferOperation,
            LinearPatternOperation,
            CircularPatternOperation,
            MirrorOperation,
            ShellOperation,
            ThroughHoleOperation,
            BlindHoleOperation,
            CounterboreHoleOperation,
            CountersinkHoleOperation,
            BossOperation,
            RibOperation,
            RectangularHolePatternOperation,
            CircularHolePatternOperation,
        ),
    ):
        errors.extend(_require_kind(object_kinds, operation.target_id, "solid", prefix, "target_id"))

    return errors


def _require_kind(
    object_kinds: dict[str, str],
    object_id: str,
    expected_kind: str,
    prefix: str,
    field_name: str,
) -> list[str]:
    if object_id not in object_kinds:
        return [f"{prefix}.{field_name} references unknown or future id '{object_id}'."]
    actual_kind = object_kinds[object_id]
    if actual_kind != expected_kind:
        return [
            f"{prefix}.{field_name} references '{object_id}', which is a {actual_kind}; "
            f"expected {expected_kind}."
        ]
    return []


def _output_kind(operation: object) -> str:
    if isinstance(operation, (CreateSketchOperation, CreateSketchRectangleOperation, CreateSketchCircleOperation)):
        return "sketch"
    return "solid"


def _positive(errors: list[str], prefix: str, field_name: str, value: float) -> None:
    if value <= 0:
        errors.append(f"{prefix}.{field_name} must be greater than 0.")


def _validate_sketch_operation(operation: CreateSketchOperation, prefix: str) -> list[str]:
    errors: list[str] = []
    sketch = operation.sketch
    if not sketch.id.strip():
        errors.append(f"{prefix}.sketch.id must not be empty.")
    if sketch.id != operation.id:
        errors.append(f"{prefix}.sketch.id must match operation id for registry compatibility.")
    if not sketch.entities:
        errors.append(f"{prefix}.sketch.entities must contain at least one entity.")
    if sketch.closed and any(isinstance(entity, (LineEntity, ArcEntity)) for entity in sketch.entities):
        errors.append(f"{prefix}.sketch.closed profiles cannot contain standalone line or arc entities.")
    for entity_index, entity in enumerate(sketch.entities, start=1):
        entity_prefix = f"{prefix}.sketch.entities[{entity_index}]"
        if isinstance(entity, LineEntity):
            if entity.start == entity.end:
                errors.append(f"{entity_prefix} line start and end must differ.")
        elif isinstance(entity, PolylineEntity):
            if len(entity.points) < 2:
                errors.append(f"{entity_prefix}.points must contain at least two points.")
            for first, second in zip(entity.points, entity.points[1:]):
                if first == second:
                    errors.append(f"{entity_prefix}.points must not contain duplicate adjacent points.")
        elif isinstance(entity, RectangleEntity):
            _positive(errors, entity_prefix, "width_mm", entity.width_mm)
            _positive(errors, entity_prefix, "height_mm", entity.height_mm)
        elif isinstance(entity, CircleEntity):
            _positive(errors, entity_prefix, "diameter_mm", entity.diameter_mm)
        elif isinstance(entity, ArcEntity):
            if len({entity.start, entity.mid, entity.end}) < 3:
                errors.append(f"{entity_prefix} arc points must be distinct.")
        elif isinstance(entity, PolygonEntity):
            _positive(errors, entity_prefix, "radius_mm", entity.radius_mm)
            if entity.sides < 3:
                errors.append(f"{entity_prefix}.sides must be at least 3.")
        elif isinstance(entity, SlotEntity):
            _positive(errors, entity_prefix, "length_mm", entity.length_mm)
            _positive(errors, entity_prefix, "width_mm", entity.width_mm)
            if entity.length_mm <= entity.width_mm:
                errors.append(f"{entity_prefix}.length_mm must be greater than width_mm.")
    return errors
