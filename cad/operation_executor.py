from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import cadquery as cq

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
    FaceSelector,
    FilletOperation,
    LineEntity,
    LinearPatternOperation,
    LoftOperation,
    MirrorOperation,
    OperationPlan,
    OperationSpec,
    PolygonEntity,
    PolylineEntity,
    RectangleEntity,
    RectangularHolePatternOperation,
    RibOperation,
    RevolveOperation,
    ShellOperation,
    SketchPlan,
    SlotEntity,
    SweepOperation,
    ThroughHoleOperation,
)
from cad.operations import export_step
from cad.operation_validator import validate_operation_plan
from parametrics.resolver import resolved_model


class OperationExecutionError(RuntimeError):
    """Raised when a validated operation plan fails during deterministic execution."""


@dataclass(frozen=True)
class RegistryObject:
    kind: str
    workplane: cq.Workplane
    source: OperationSpec | None = None


@dataclass(frozen=True)
class OperationExecutionResult:
    final_object_id: str
    final_object: cq.Workplane
    objects: dict[str, RegistryObject]


def execute_operation_plan(plan: OperationPlan) -> OperationExecutionResult:
    """Execute a validated operation plan and return the final solid."""

    plan = resolved_model(plan)  # type: ignore[assignment]
    validate_operation_plan(plan)
    objects: dict[str, RegistryObject] = {}

    for operation in plan.operations:
        objects[operation.id] = _execute_operation(operation, objects)

    final_object_id = plan.final_object_id or plan.operations[-1].id
    final = objects[final_object_id]
    if final.kind != "solid":
        raise OperationExecutionError(f"Final object '{final_object_id}' is not a solid.")

    final_shape = _as_exportable_solid(final.workplane)
    _validate_non_empty_solid(final_shape, final_object_id)
    objects[final_object_id] = RegistryObject(kind="solid", workplane=final_shape, source=final.source)
    return OperationExecutionResult(final_object_id, final_shape, objects)


def export_operation_plan_step(
    plan: OperationPlan,
    output_path: str | Path,
) -> Path:
    """Execute an operation plan and export the final object to STEP."""

    result = execute_operation_plan(plan)
    return export_step(result.final_object, output_path)


def default_operation_output_path(plan: OperationPlan) -> Path:
    """Return a project-name-based STEP path inside outputs."""

    safe_name = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in plan.project_name)
    safe_name = safe_name.strip("_") or "operation_plan"
    return Path("outputs") / f"{safe_name}.step"


def _execute_operation(
    operation: OperationSpec,
    objects: dict[str, RegistryObject],
) -> RegistryObject:
    if isinstance(operation, CreateBoxOperation):
        return RegistryObject("solid", _create_box(operation), operation)
    if isinstance(operation, CreateCylinderOperation):
        return RegistryObject("solid", _create_cylinder(operation), operation)
    if isinstance(operation, CreateSketchOperation):
        return RegistryObject("sketch", _create_structured_sketch(operation.sketch), operation)
    if isinstance(operation, CreateSketchRectangleOperation):
        return RegistryObject("sketch", _create_sketch_rectangle(operation), operation)
    if isinstance(operation, CreateSketchCircleOperation):
        return RegistryObject("sketch", _create_sketch_circle(operation), operation)
    if isinstance(operation, ExtrudeOperation):
        distance = operation.distance_mm if operation.direction == "positive" else -operation.distance_mm
        return RegistryObject(
            "solid",
            _as_single_solid(
                objects[operation.sketch_id].workplane.extrude(
                    distance,
                    both=operation.symmetric,
                )
            ),
            operation,
        )
    if isinstance(operation, RevolveOperation):
        solid = _revolve(objects[operation.sketch_id], operation)
        return RegistryObject("solid", _as_single_solid(solid), operation)
    if isinstance(operation, CutHoleOperation):
        return RegistryObject("solid", _cut_hole(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, CutExtrudeOperation):
        return RegistryObject("solid", _cut_extrude(objects, operation), operation)
    if isinstance(operation, LoftOperation):
        return RegistryObject("solid", _loft(objects, operation), operation)
    if isinstance(operation, SweepOperation):
        return RegistryObject("solid", _sweep(objects, operation), operation)
    if isinstance(operation, ShellOperation):
        return RegistryObject("solid", _shell(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, (ThroughHoleOperation, BlindHoleOperation, CounterboreHoleOperation, CountersinkHoleOperation)):
        return RegistryObject("solid", _advanced_hole(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, BossOperation):
        return RegistryObject("solid", _boss(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, RibOperation):
        return RegistryObject("solid", _rib(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, RectangularHolePatternOperation):
        return RegistryObject("solid", _rectangular_hole_pattern(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, CircularHolePatternOperation):
        return RegistryObject("solid", _circular_hole_pattern(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, BooleanUnionOperation):
        solid = objects[operation.target_id].workplane.union(objects[operation.tool_id].workplane)
        return RegistryObject("solid", _as_single_solid(solid), operation)
    if isinstance(operation, BooleanCutOperation):
        solid = objects[operation.target_id].workplane.cut(objects[operation.tool_id].workplane)
        return RegistryObject("solid", _as_single_solid(solid), operation)
    if isinstance(operation, FilletOperation):
        solid = _select_edges(objects[operation.target_id].workplane, operation.edge_selector).fillet(operation.radius_mm)
        return RegistryObject("solid", _as_single_solid(solid), operation)
    if isinstance(operation, ChamferOperation):
        solid = _select_edges(objects[operation.target_id].workplane, operation.edge_selector).chamfer(operation.distance_mm)
        return RegistryObject("solid", _as_single_solid(solid), operation)
    if isinstance(operation, LinearPatternOperation):
        return RegistryObject("solid", _linear_pattern(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, CircularPatternOperation):
        return RegistryObject("solid", _circular_pattern(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, MirrorOperation):
        return RegistryObject("solid", _mirror(objects[operation.target_id].workplane, operation), operation)
    if isinstance(operation, ExternalCapabilityOperation):
        return RegistryObject("solid", _external_capability(operation), operation)
    raise OperationExecutionError(f"Unsupported operation: {type(operation).__name__}")


def _create_box(operation: CreateBoxOperation) -> cq.Workplane:
    return _as_single_solid(
        cq.Workplane("XY")
        .box(operation.width_mm, operation.depth_mm, operation.height_mm)
        .translate(operation.center)
    )


def _create_cylinder(operation: CreateCylinderOperation) -> cq.Workplane:
    part = cq.Workplane("XY").circle(operation.diameter_mm / 2).extrude(operation.height_mm)
    part = part.translate((0, 0, -operation.height_mm / 2))
    part = _orient_from_z_axis(part, operation.axis)
    return _as_single_solid(part.translate(operation.center))


def _create_sketch_rectangle(operation: CreateSketchRectangleOperation) -> cq.Workplane:
    return cq.Workplane(operation.plane, origin=operation.center).rect(
        operation.width_mm,
        operation.height_mm,
    )


def _create_sketch_circle(operation: CreateSketchCircleOperation) -> cq.Workplane:
    return cq.Workplane(operation.plane, origin=operation.center).circle(operation.diameter_mm / 2)


def _create_structured_sketch(sketch: SketchPlan) -> cq.Workplane:
    workplane = cq.Workplane(sketch.plane, origin=sketch.origin)
    for entity in sketch.entities:
        if isinstance(entity, LineEntity):
            workplane = workplane.moveTo(*entity.start).lineTo(*entity.end)
        elif isinstance(entity, PolylineEntity):
            workplane = workplane.moveTo(*entity.points[0])
            for point in entity.points[1:]:
                workplane = workplane.lineTo(*point)
            if entity.closed:
                workplane = workplane.close()
        elif isinstance(entity, RectangleEntity):
            workplane = workplane.center(*entity.center).rect(entity.width_mm, entity.height_mm).center(
                -entity.center[0],
                -entity.center[1],
            )
        elif isinstance(entity, CircleEntity):
            workplane = workplane.center(*entity.center).circle(entity.diameter_mm / 2).center(
                -entity.center[0],
                -entity.center[1],
            )
        elif isinstance(entity, ArcEntity):
            workplane = workplane.moveTo(*entity.start).threePointArc(entity.mid, entity.end)
        elif isinstance(entity, PolygonEntity):
            workplane = _add_polygon(workplane, entity)
        elif isinstance(entity, SlotEntity):
            workplane = workplane.center(*entity.center).slot2D(
                entity.length_mm,
                entity.width_mm,
                angle=entity.rotation_deg,
            ).center(-entity.center[0], -entity.center[1])
        else:
            raise OperationExecutionError(f"Unsupported sketch entity: {type(entity).__name__}")
    return workplane


def _add_polygon(workplane: cq.Workplane, entity: PolygonEntity) -> cq.Workplane:
    points: list[tuple[float, float]] = []
    rotation = math.radians(entity.rotation_deg)
    for index in range(entity.sides):
        angle = rotation + (2 * math.pi * index / entity.sides)
        points.append(
            (
                entity.center[0] + entity.radius_mm * math.cos(angle),
                entity.center[1] + entity.radius_mm * math.sin(angle),
            )
        )
    result = workplane.moveTo(*points[0])
    for point in points[1:]:
        result = result.lineTo(*point)
    return result.close()


def _cut_hole(target: cq.Workplane, operation: CutHoleOperation) -> cq.Workplane:
    if operation.direction == "z":
        x_mm, y_mm = operation.position
        workplane = target.faces(">Z").workplane().center(x_mm, y_mm)
        if operation.depth_mm is None:
            return _as_single_solid(workplane.hole(operation.diameter_mm))
        return _as_single_solid(workplane.hole(operation.diameter_mm, operation.depth_mm))

    cutter = _hole_cutter(target, operation)
    return _as_single_solid(target.cut(cutter))


def _cut_extrude(objects: dict[str, RegistryObject], operation: CutExtrudeOperation) -> cq.Workplane:
    target = objects[operation.target_id].workplane
    sketch = objects[operation.sketch_id].workplane
    distance = operation.distance_mm
    if operation.extent_type == "through_all":
        bbox = target.val().BoundingBox()
        distance = max(bbox.xlen, bbox.ylen, bbox.zlen) * 3 + 10
    if distance is None:
        raise OperationExecutionError("cut_extrude distance is required for blind cuts.")
    signed_distance = distance if operation.direction == "positive" else -distance
    cutter = sketch.extrude(signed_distance)
    return _as_single_solid(target.cut(cutter))


def _loft(objects: dict[str, RegistryObject], operation: LoftOperation) -> cq.Workplane:
    sketches = [_require_structured_sketch(objects[sketch_id], sketch_id) for sketch_id in operation.sketch_ids]
    first = sketches[0]
    if any(sketch.plane != first.plane for sketch in sketches):
        raise OperationExecutionError("Loft sketches must use the same base plane.")
    workplane = _simple_profile_workplane(first)
    previous_origin = first.origin
    for sketch in sketches[1:]:
        offset = _plane_offset(first.plane, previous_origin, sketch.origin)
        workplane = _add_profile(workplane.workplane(offset=offset), sketch)
        previous_origin = sketch.origin
    try:
        return _as_single_solid(workplane.loft(combine=True, ruled=operation.ruled))
    except Exception as exc:
        raise OperationExecutionError(f"loft failure: {exc}") from exc


def _sweep(objects: dict[str, RegistryObject], operation: SweepOperation) -> cq.Workplane:
    profile = objects[operation.profile_sketch_id].workplane
    path = objects[operation.path_sketch_id].workplane
    try:
        return _as_single_solid(profile.sweep(path, isFrenet=True, makeSolid=operation.make_solid))
    except Exception as exc:
        raise OperationExecutionError(f"sweep failure: {exc}") from exc


def _shell(target: cq.Workplane, operation: ShellOperation) -> cq.Workplane:
    bbox = target.val().BoundingBox()
    if operation.thickness_mm >= min(bbox.xlen, bbox.ylen, bbox.zlen) / 2:
        raise OperationExecutionError("shell failure: thickness is too large for the target bounding box.")
    try:
        selected = _select_faces(target, operation.remove_face_selector) if operation.remove_face_selector else target
        return _as_single_solid(selected.shell(operation.thickness_mm))
    except Exception as exc:
        raise OperationExecutionError(f"shell failure: {exc}") from exc


def _advanced_hole(
    target: cq.Workplane,
    operation: ThroughHoleOperation | BlindHoleOperation | CounterboreHoleOperation | CountersinkHoleOperation,
) -> cq.Workplane:
    if operation.face_selector != "top_face":
        raise OperationExecutionError("hole feature failure: only top_face holes are currently supported.")
    _validate_xy_position_inside(target, operation.position, operation.hole_diameter_mm)
    workplane = target.faces(">Z").workplane().center(*operation.position)
    try:
        if isinstance(operation, ThroughHoleOperation):
            return _as_single_solid(workplane.hole(operation.hole_diameter_mm))
        if isinstance(operation, BlindHoleOperation):
            return _as_single_solid(workplane.hole(operation.hole_diameter_mm, operation.depth_mm))
        if isinstance(operation, CounterboreHoleOperation):
            return _as_single_solid(
                workplane.cboreHole(
                    operation.hole_diameter_mm,
                    operation.counterbore_diameter_mm,
                    operation.counterbore_depth_mm,
                )
            )
        if isinstance(operation, CountersinkHoleOperation):
            return _as_single_solid(
                workplane.cskHole(
                    operation.hole_diameter_mm,
                    operation.countersink_diameter_mm,
                    operation.angle_deg,
                )
            )
    except Exception as exc:
        raise OperationExecutionError(f"hole feature failure: {exc}") from exc
    raise OperationExecutionError(f"Unsupported hole operation: {type(operation).__name__}")


def _boss(target: cq.Workplane, operation: BossOperation) -> cq.Workplane:
    if operation.face_selector != "top_face":
        raise OperationExecutionError("Only top_face bosses are currently supported.")
    bbox = target.val().BoundingBox()
    _validate_xy_position_inside(target, operation.position, operation.diameter_mm)
    boss = (
        cq.Workplane("XY")
        .circle(operation.diameter_mm / 2)
        .extrude(operation.height_mm)
        .translate((operation.position[0], operation.position[1], bbox.zmax))
    )
    return _as_single_solid(target.union(boss))


def _rib(target: cq.Workplane, operation: RibOperation) -> cq.Workplane:
    if operation.face_selector != "top_face":
        raise OperationExecutionError("Only top_face ribs are currently supported.")
    bbox = target.val().BoundingBox()
    dx = operation.end[0] - operation.start[0]
    dy = operation.end[1] - operation.start[1]
    length = math.hypot(dx, dy)
    if length <= 0:
        raise OperationExecutionError("Rib length must be positive.")
    angle = math.degrees(math.atan2(dy, dx))
    center = ((operation.start[0] + operation.end[0]) / 2, (operation.start[1] + operation.end[1]) / 2)
    rib = (
        cq.Workplane("XY")
        .box(length, operation.thickness_mm, operation.height_mm)
        .translate((0, 0, operation.height_mm / 2))
        .rotate((0, 0, 0), (0, 0, 1), angle)
        .translate((center[0], center[1], bbox.zmax))
    )
    return _as_single_solid(target.union(rib))


def _rectangular_hole_pattern(target: cq.Workplane, operation: RectangularHolePatternOperation) -> cq.Workplane:
    result = target
    x0 = operation.center[0] - operation.spacing_x_mm * (operation.count_x - 1) / 2
    y0 = operation.center[1] - operation.spacing_y_mm * (operation.count_y - 1) / 2
    for ix in range(operation.count_x):
        for iy in range(operation.count_y):
            hole = ThroughHoleOperation(
                id=f"{operation.id}_{ix}_{iy}",
                target_id=operation.target_id,
                position=(x0 + ix * operation.spacing_x_mm, y0 + iy * operation.spacing_y_mm),
                hole_diameter_mm=operation.hole_diameter_mm,
                face_selector=operation.face_selector,
            )
            result = _advanced_hole(result, hole)
    return result


def _circular_hole_pattern(target: cq.Workplane, operation: CircularHolePatternOperation) -> cq.Workplane:
    result = target
    for index in range(operation.count):
        angle = math.radians(operation.start_angle_deg + 360 * index / operation.count)
        position = (
            operation.center[0] + operation.radius_mm * math.cos(angle),
            operation.center[1] + operation.radius_mm * math.sin(angle),
        )
        hole = ThroughHoleOperation(
            id=f"{operation.id}_{index}",
            target_id=operation.target_id,
            position=position,
            hole_diameter_mm=operation.hole_diameter_mm,
            face_selector=operation.face_selector,
        )
        result = _advanced_hole(result, hole)
    return result


def _revolve(sketch: RegistryObject, operation: RevolveOperation) -> cq.Workplane:
    if operation.angle_deg != 360:
        raise OperationExecutionError("Only full 360-degree revolve is supported in this milestone.")
    if operation.axis != "z":
        raise OperationExecutionError("Only Z-axis revolve is supported in this milestone.")
    if not isinstance(sketch.source, CreateSketchRectangleOperation):
        raise OperationExecutionError("Only rectangular sketches can be revolved in this milestone.")
    if sketch.source.plane not in {"XZ", "YZ"}:
        raise OperationExecutionError("Z-axis revolve requires an XZ or YZ rectangle profile.")

    center = sketch.source.center
    radial_center = abs(center[0] if sketch.source.plane == "XZ" else center[1])
    outer_radius = radial_center + sketch.source.width_mm / 2
    inner_radius = radial_center - sketch.source.width_mm / 2
    if outer_radius <= 0 or inner_radius < 0:
        raise OperationExecutionError("Revolved rectangle must sit on or outside the revolve axis.")

    height = sketch.source.height_mm
    part = cq.Workplane("XY").circle(outer_radius).extrude(height)
    part = part.translate((0, 0, center[2] - height / 2))
    if inner_radius > 0:
        cutter = cq.Workplane("XY").circle(inner_radius).extrude(height + 2)
        cutter = cutter.translate((0, 0, center[2] - height / 2 - 1))
        part = part.cut(cutter)
    return _as_single_solid(part)


def _hole_cutter(target: cq.Workplane, operation: CutHoleOperation) -> cq.Workplane:
    bbox = target.val().BoundingBox()
    length = operation.depth_mm or max(bbox.xlen, bbox.ylen, bbox.zlen) + 2
    cutter = cq.Workplane("XY").circle(operation.diameter_mm / 2).extrude(length)
    cutter = cutter.translate((0, 0, -length / 2))
    cutter = _orient_from_z_axis(cutter, operation.direction)

    first, second = operation.position
    if operation.direction == "x":
        center = ((bbox.xmin + bbox.xmax) / 2, first, second)
    else:
        center = (first, (bbox.ymin + bbox.ymax) / 2, second)
    return cutter.translate(center)


def _require_structured_sketch(registry_object: RegistryObject, sketch_id: str) -> SketchPlan:
    if not isinstance(registry_object.source, CreateSketchOperation):
        raise OperationExecutionError(f"Operation '{sketch_id}' must be a create_sketch operation.")
    if not registry_object.source.sketch.closed:
        raise OperationExecutionError(f"Sketch '{sketch_id}' must be closed.")
    return registry_object.source.sketch


def _simple_profile_workplane(sketch: SketchPlan) -> cq.Workplane:
    return _add_profile(cq.Workplane(sketch.plane, origin=sketch.origin), sketch)


def _add_profile(workplane: cq.Workplane, sketch: SketchPlan) -> cq.Workplane:
    if len(sketch.entities) != 1:
        raise OperationExecutionError("Loft profiles currently support exactly one entity per sketch.")
    entity = sketch.entities[0]
    if isinstance(entity, RectangleEntity):
        return workplane.center(*entity.center).rect(entity.width_mm, entity.height_mm).center(
            -entity.center[0],
            -entity.center[1],
        )
    if isinstance(entity, CircleEntity):
        return workplane.center(*entity.center).circle(entity.diameter_mm / 2).center(
            -entity.center[0],
            -entity.center[1],
        )
    if isinstance(entity, PolygonEntity):
        return _add_polygon(workplane, entity)
    raise OperationExecutionError("Loft profiles currently support circle, rectangle, or polygon entities.")


def _plane_offset(plane: str, previous_origin: tuple[float, float, float], origin: tuple[float, float, float]) -> float:
    if plane == "XY":
        return origin[2] - previous_origin[2]
    if plane == "XZ":
        return origin[1] - previous_origin[1]
    if plane == "YZ":
        return origin[0] - previous_origin[0]
    raise OperationExecutionError(f"Unsupported sketch plane '{plane}'.")


def _select_faces(part: cq.Workplane, selector: FaceSelector | None) -> cq.Workplane:
    if selector is None or selector == "all_faces":
        return part.faces()
    mapping = {
        "top_face": ">Z",
        "bottom_face": "<Z",
        "front_face": ">Y",
        "back_face": "<Y",
        "left_face": "<X",
        "right_face": ">X",
    }
    if selector not in mapping:
        raise OperationExecutionError(f"Unsupported face selector '{selector}'.")
    return part.faces(mapping[selector])


def _select_edges(part: cq.Workplane, selector: str) -> cq.Workplane:
    if selector == "all_edges":
        return part.edges()
    if selector == "vertical_edges":
        return part.edges("|Z")
    if selector == "horizontal_edges":
        return part.edges("#Z")
    if selector == "top_edges":
        return part.faces(">Z").edges()
    if selector == "bottom_edges":
        return part.faces("<Z").edges()
    if selector == "outer_edges":
        return part.edges()
    raise OperationExecutionError(f"Unsupported edge selector '{selector}'.")


def _validate_xy_position_inside(target: cq.Workplane, position: tuple[float, float], diameter_mm: float) -> None:
    bbox = target.val().BoundingBox()
    radius = diameter_mm / 2
    x, y = position
    if x - radius < bbox.xmin or x + radius > bbox.xmax or y - radius < bbox.ymin or y + radius > bbox.ymax:
        raise OperationExecutionError("hole feature failure: hole position is outside target bounds.")


def _linear_pattern(part: cq.Workplane, operation: LinearPatternOperation) -> cq.Workplane:
    result = part
    direction = _direction_vector(operation.direction)
    for index in range(1, operation.count):
        offset = tuple(component * operation.spacing_mm * index for component in direction)
        result = result.union(part.translate(offset))
    return _as_exportable_solid(result)


def _circular_pattern(part: cq.Workplane, operation: CircularPatternOperation) -> cq.Workplane:
    result = part
    step = operation.angle_deg / operation.count
    axis_start, axis_end = _axis_points(operation.axis)
    for index in range(1, operation.count):
        result = result.union(part.rotate(axis_start, axis_end, step * index))
    return _as_exportable_solid(result)


def _mirror(part: cq.Workplane, operation: MirrorOperation) -> cq.Workplane:
    if operation.plane == "YZ":
        mirrored = part.mirror("YZ")
    elif operation.plane == "XZ":
        mirrored = part.mirror("XZ")
    elif operation.plane == "XY":
        mirrored = part.mirror("XY")
    else:
        raise OperationExecutionError(f"Unsupported mirror plane '{operation.plane}'.")
    return _as_exportable_solid(part.union(mirrored))


def _external_capability(operation: ExternalCapabilityOperation) -> cq.Workplane:
    from capabilities.invocation import CapabilityInvocationError, invoke_capability

    try:
        response = invoke_capability(operation.capability_id, operation.arguments)
    except CapabilityInvocationError as exc:
        raise OperationExecutionError(f"external capability failure: {exc}") from exc
    result = response.result
    if result.get("result_type") != "geometry":
        raise OperationExecutionError("external capability did not return a geometry result.")
    step_path = result.get("step_path")
    if not isinstance(step_path, str):
        raise OperationExecutionError("external capability geometry result did not include a STEP path.")
    try:
        imported = cq.importers.importStep(step_path)
    except Exception as exc:
        raise OperationExecutionError(f"external capability STEP import failed: {exc}") from exc
    return _as_exportable_solid(imported)


def _orient_from_z_axis(part: cq.Workplane, axis: str) -> cq.Workplane:
    if axis == "z":
        return part
    if axis == "x":
        return part.rotate((0, 0, 0), (0, 1, 0), 90)
    if axis == "y":
        return part.rotate((0, 0, 0), (1, 0, 0), 90)
    raise OperationExecutionError(f"Unsupported axis '{axis}'.")


def _direction_vector(axis: str) -> tuple[int, int, int]:
    if axis == "x":
        return (1, 0, 0)
    if axis == "y":
        return (0, 1, 0)
    if axis == "z":
        return (0, 0, 1)
    raise OperationExecutionError(f"Unsupported axis '{axis}'.")


def _axis_points(axis: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    if axis == "x":
        return (0, 0, 0), (1, 0, 0)
    if axis == "y":
        return (0, 0, 0), (0, 1, 0)
    if axis == "z":
        return (0, 0, 0), (0, 0, 1)
    raise OperationExecutionError(f"Unsupported axis '{axis}'.")


def _as_single_solid(part: cq.Workplane) -> cq.Workplane:
    shape = part.val()
    if isinstance(shape, cq.Solid):
        return cq.Workplane("XY").newObject([shape])
    solids = shape.Solids()
    if len(solids) != 1:
        raise OperationExecutionError(f"Expected one solid, found {len(solids)}.")
    return cq.Workplane("XY").newObject([solids[0]])


def _as_exportable_solid(part: cq.Workplane) -> cq.Workplane:
    shape = part.val()
    if isinstance(shape, cq.Solid):
        return cq.Workplane("XY").newObject([shape])
    solids = shape.Solids()
    if not solids:
        raise OperationExecutionError("Expected at least one solid, found none.")
    return cq.Workplane("XY").newObject([shape])


def _validate_non_empty_solid(part: cq.Workplane, object_id: str) -> None:
    try:
        volume = part.val().Volume()
    except Exception as exc:
        raise OperationExecutionError(f"Final object '{object_id}' is not a measurable solid.") from exc
    if volume <= 0:
        raise OperationExecutionError(f"Final object '{object_id}' has no positive volume.")
